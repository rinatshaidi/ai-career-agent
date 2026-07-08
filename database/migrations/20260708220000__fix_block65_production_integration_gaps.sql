BEGIN;

UPDATE user_profiles
SET
    profile_data = jsonb_set(
        COALESCE(profile_data, '{}'::jsonb),
        '{telegram_delivery,bot_name}',
        to_jsonb('Ri Career Agent'::text),
        true
    ),
    updated_at = now()
WHERE jsonb_typeof(COALESCE(profile_data, '{}'::jsonb)) = 'object'
  AND profile_data ? 'telegram_delivery'
  AND COALESCE(NULLIF(trim(profile_data #>> '{telegram_delivery,bot_name}'), ''), 'Ri assistant') = 'Ri assistant';

CREATE OR REPLACE FUNCTION delivery_upsert_telegram_target(
    p_user_id uuid,
    p_chat_id text,
    p_delivery_enabled boolean DEFAULT true,
    p_bot_name text DEFAULT 'Ri Career Agent'
)
RETURNS TABLE (
    user_id uuid,
    chat_id text,
    delivery_enabled boolean,
    bot_name text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_data jsonb;
BEGIN
    INSERT INTO user_profiles (
        user_id,
        profile_data
    )
    VALUES (
        p_user_id,
        jsonb_build_object(
            'telegram_delivery',
            jsonb_build_object(
                'chat_id', NULLIF(trim(p_chat_id), ''),
                'enabled', COALESCE(p_delivery_enabled, true),
                'bot_name', COALESCE(NULLIF(trim(p_bot_name), ''), 'Ri Career Agent')
            )
        )
    )
    ON CONFLICT (user_id)
    DO UPDATE SET
        profile_data = jsonb_set(
            COALESCE(user_profiles.profile_data, '{}'::jsonb),
            '{telegram_delivery}',
            jsonb_build_object(
                'chat_id', NULLIF(trim(p_chat_id), ''),
                'enabled', COALESCE(p_delivery_enabled, true),
                'bot_name', COALESCE(NULLIF(trim(p_bot_name), ''), 'Ri Career Agent')
            ),
            true
        ),
        updated_at = now()
    RETURNING user_profiles.profile_data
    INTO v_profile_data;

    RETURN QUERY
    SELECT
        p_user_id,
        v_profile_data #>> '{telegram_delivery,chat_id}',
        COALESCE((v_profile_data #>> '{telegram_delivery,enabled}')::boolean, false),
        COALESCE(v_profile_data #>> '{telegram_delivery,bot_name}', 'Ri Career Agent');
END;
$$;

CREATE OR REPLACE FUNCTION delivery_sync_telegram_outbox(
    p_profile_slug text DEFAULT NULL
)
RETURNS TABLE (
    created_count integer,
    cancelled_count integer,
    existing_count integer
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_created_count integer := 0;
    v_cancelled_count integer := 0;
    v_existing_count integer := 0;
BEGIN
    WITH eligible AS (
        SELECT
            users.id AS user_id,
            opportunity_ai_analysis.opportunity_id,
            opportunity_ai_analysis.user_intelligence_profile_id,
            opportunity_ai_analysis.id AS analysis_id,
            opportunity_ai_analysis.recommended_action,
            opportunity_ai_analysis.opportunity_score,
            trim(COALESCE(user_profiles.profile_data #>> '{telegram_delivery,chat_id}', '')) AS chat_id,
            COALESCE((user_profiles.profile_data #>> '{telegram_delivery,enabled}')::boolean, true) AS delivery_enabled,
            COALESCE(user_profiles.profile_data #>> '{telegram_delivery,bot_name}', 'Ri Career Agent') AS bot_name,
            opportunities.title,
            opportunities.url,
            opportunities.opportunity_type,
            sources.name AS source_name,
            sources.type AS source_catalog_type
        FROM opportunity_ai_analysis
        JOIN user_intelligence_profiles
            ON user_intelligence_profiles.id = opportunity_ai_analysis.user_intelligence_profile_id
        JOIN users
            ON users.id = user_intelligence_profiles.user_id
        LEFT JOIN user_profiles
            ON user_profiles.user_id = users.id
        JOIN opportunities
            ON opportunities.id = opportunity_ai_analysis.opportunity_id
        JOIN sources
            ON sources.id = opportunities.source_id
        WHERE opportunity_ai_analysis.is_current
          AND user_intelligence_profiles.status = 'active'
          AND users.status = 'active'
          AND opportunities.status = 'analyzed'
          AND opportunity_ai_analysis.recommended_action IN ('apply_now', 'review_manually', 'watchlist')
          AND (p_profile_slug IS NULL OR user_intelligence_profiles.profile_slug = p_profile_slug)
          AND trim(COALESCE(user_profiles.profile_data #>> '{telegram_delivery,chat_id}', '')) <> ''
          AND COALESCE((user_profiles.profile_data #>> '{telegram_delivery,enabled}')::boolean, true)
    ),
    cancelled AS (
        UPDATE notifications
        SET
            status = 'cancelled',
            error_message = 'Notification became ineligible before delivery.',
            locked_at = NULL,
            locked_by = NULL,
            updated_at = now()
        WHERE notifications.channel = 'telegram'
          AND notifications.notification_type = 'opportunity_match'
          AND notifications.status IN ('pending', 'retry')
          AND notifications.user_intelligence_profile_id IS NOT NULL
          AND (p_profile_slug IS NULL OR EXISTS (
              SELECT 1
              FROM user_intelligence_profiles
              WHERE user_intelligence_profiles.id = notifications.user_intelligence_profile_id
                AND user_intelligence_profiles.profile_slug = p_profile_slug
          ))
          AND NOT EXISTS (
              SELECT 1
              FROM eligible
              WHERE eligible.user_id = notifications.user_id
                AND eligible.opportunity_id = notifications.opportunity_id
                AND eligible.user_intelligence_profile_id = notifications.user_intelligence_profile_id
          )
        RETURNING notifications.id
    ),
    inserted AS (
        INSERT INTO notifications (
            user_id,
            opportunity_id,
            user_intelligence_profile_id,
            channel,
            notification_type,
            payload,
            status,
            next_attempt_at
        )
        SELECT
            eligible.user_id,
            eligible.opportunity_id,
            eligible.user_intelligence_profile_id,
            'telegram',
            'opportunity_match',
            jsonb_build_object(
                'delivery_key',
                concat_ws(
                    ':',
                    'telegram',
                    'opportunity_match',
                    eligible.user_id::text,
                    eligible.user_intelligence_profile_id::text,
                    eligible.opportunity_id::text
                ),
                'analysis_id', eligible.analysis_id,
                'recommended_action', eligible.recommended_action,
                'opportunity_score', eligible.opportunity_score,
                'target', jsonb_build_object(
                    'chat_id', eligible.chat_id,
                    'bot_name', eligible.bot_name
                ),
                'source_snapshot', jsonb_build_object(
                    'source_name', eligible.source_name,
                    'source_type', eligible.source_catalog_type
                ),
                'message_version', 'block5-v1'
            ),
            'pending',
            now()
        FROM eligible
        WHERE NOT EXISTS (
            SELECT 1
            FROM notifications
            WHERE notifications.user_id = eligible.user_id
              AND notifications.opportunity_id = eligible.opportunity_id
              AND notifications.user_intelligence_profile_id = eligible.user_intelligence_profile_id
              AND notifications.channel = 'telegram'
              AND notifications.notification_type = 'opportunity_match'
        )
        ON CONFLICT DO NOTHING
        RETURNING notifications.id
    )
    SELECT
        COALESCE((SELECT COUNT(*) FROM inserted), 0),
        COALESCE((SELECT COUNT(*) FROM cancelled), 0),
        COALESCE((
            SELECT COUNT(*)
            FROM eligible
            WHERE EXISTS (
                SELECT 1
                FROM notifications
                WHERE notifications.user_id = eligible.user_id
                  AND notifications.opportunity_id = eligible.opportunity_id
                  AND notifications.user_intelligence_profile_id = eligible.user_intelligence_profile_id
                  AND notifications.channel = 'telegram'
                  AND notifications.notification_type = 'opportunity_match'
            )
        ), 0)
    INTO
        v_created_count,
        v_cancelled_count,
        v_existing_count;

    RETURN QUERY
    SELECT
        v_created_count,
        v_cancelled_count,
        GREATEST(v_existing_count - v_created_count, 0);
END;
$$;

CREATE OR REPLACE FUNCTION delivery_claim_notification_batch(
    p_batch_size integer DEFAULT 10,
    p_lock_token text DEFAULT NULL,
    p_lock_timeout_minutes integer DEFAULT 30
)
RETURNS TABLE (
    notification_id uuid,
    user_id uuid,
    opportunity_id uuid,
    user_intelligence_profile_id uuid,
    chat_id text,
    bot_name text,
    title text,
    company_name text,
    source_name text,
    opportunity_type text,
    source_type text,
    opportunity_score numeric,
    recommended_action text,
    why_fit jsonb,
    why_not_fit jsonb,
    risks jsonb,
    budget_min numeric,
    budget_max numeric,
    currency char(3),
    url text,
    location text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_lock_token text := COALESCE(NULLIF(trim(p_lock_token), ''), gen_random_uuid()::text);
    v_batch_size integer := GREATEST(COALESCE(p_batch_size, 10), 1);
    v_lock_timeout_minutes integer := GREATEST(COALESCE(p_lock_timeout_minutes, 30), 1);
BEGIN
    UPDATE notifications
    SET
        status = 'retry',
        locked_at = NULL,
        locked_by = NULL,
        next_attempt_at = now(),
        updated_at = now()
    WHERE notifications.channel = 'telegram'
      AND notifications.notification_type = 'opportunity_match'
      AND notifications.status = 'in_progress'
      AND notifications.locked_at IS NOT NULL
      AND notifications.locked_at <= now() - make_interval(mins => v_lock_timeout_minutes);

    RETURN QUERY
    WITH eligible AS (
        SELECT
            notifications.id AS notification_id,
            notifications.user_id,
            notifications.opportunity_id,
            notifications.user_intelligence_profile_id,
            trim(COALESCE(user_profiles.profile_data #>> '{telegram_delivery,chat_id}', '')) AS chat_id,
            COALESCE(user_profiles.profile_data #>> '{telegram_delivery,bot_name}', 'Ri Career Agent') AS bot_name,
            opportunities.title,
            opportunities.company_name,
            sources.name AS source_name,
            opportunities.opportunity_type,
            opportunities.source_type,
            opportunity_ai_analysis.opportunity_score,
            opportunity_ai_analysis.recommended_action,
            opportunity_ai_analysis.why_fit,
            opportunity_ai_analysis.why_not_fit,
            opportunity_ai_analysis.risks,
            opportunities.budget_min,
            opportunities.budget_max,
            opportunities.currency,
            opportunities.url,
            opportunities.location
        FROM notifications
        JOIN opportunity_ai_analysis
            ON opportunity_ai_analysis.opportunity_id = notifications.opportunity_id
           AND opportunity_ai_analysis.user_intelligence_profile_id = notifications.user_intelligence_profile_id
           AND opportunity_ai_analysis.is_current
        JOIN opportunities
            ON opportunities.id = notifications.opportunity_id
        JOIN sources
            ON sources.id = opportunities.source_id
        LEFT JOIN user_profiles
            ON user_profiles.user_id = notifications.user_id
        WHERE notifications.channel = 'telegram'
          AND notifications.notification_type = 'opportunity_match'
          AND notifications.status IN ('pending', 'retry')
          AND notifications.next_attempt_at <= now()
          AND trim(COALESCE(user_profiles.profile_data #>> '{telegram_delivery,chat_id}', '')) <> ''
          AND COALESCE((user_profiles.profile_data #>> '{telegram_delivery,enabled}')::boolean, true)
          AND opportunity_ai_analysis.recommended_action IN ('apply_now', 'review_manually', 'watchlist')
          AND opportunities.status = 'analyzed'
    ),
    claimable AS (
        SELECT eligible.notification_id
        FROM eligible
        JOIN notifications
            ON notifications.id = eligible.notification_id
        ORDER BY notifications.created_at
        LIMIT v_batch_size
        FOR UPDATE OF notifications SKIP LOCKED
    ),
    claimed AS (
        UPDATE notifications
        SET
            status = 'in_progress',
            attempt_count = notifications.attempt_count + 1,
            last_attempt_at = now(),
            locked_at = now(),
            locked_by = v_lock_token,
            updated_at = now()
        FROM claimable
        WHERE notifications.id = claimable.notification_id
        RETURNING notifications.id
    )
    SELECT
        eligible.notification_id,
        eligible.user_id,
        eligible.opportunity_id,
        eligible.user_intelligence_profile_id,
        eligible.chat_id,
        eligible.bot_name,
        eligible.title,
        eligible.company_name,
        eligible.source_name,
        eligible.opportunity_type,
        eligible.source_type,
        eligible.opportunity_score,
        eligible.recommended_action,
        eligible.why_fit,
        eligible.why_not_fit,
        eligible.risks,
        eligible.budget_min,
        eligible.budget_max,
        eligible.currency,
        eligible.url,
        eligible.location
    FROM eligible
    JOIN claimed
        ON claimed.id = eligible.notification_id
    ORDER BY eligible.notification_id;
END;
$$;

COMMIT;
