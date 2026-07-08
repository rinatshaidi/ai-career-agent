BEGIN;

ALTER TABLE notifications
    ADD COLUMN user_intelligence_profile_id uuid REFERENCES user_intelligence_profiles(id) ON DELETE SET NULL,
    ADD COLUMN attempt_count integer NOT NULL DEFAULT 0,
    ADD COLUMN last_attempt_at timestamptz,
    ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN locked_at timestamptz,
    ADD COLUMN locked_by text;

ALTER TABLE notifications
    DROP CONSTRAINT notifications_status_chk;

ALTER TABLE notifications
    ADD CONSTRAINT notifications_status_chk
        CHECK (status IN ('pending', 'in_progress', 'retry', 'sent', 'failed', 'cancelled'));

ALTER TABLE notifications
    ADD CONSTRAINT notifications_attempt_count_chk
        CHECK (attempt_count >= 0);

ALTER TABLE google_sheets_journal
    ADD COLUMN notification_id uuid REFERENCES notifications(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX notifications_telegram_opportunity_match_uidx
    ON notifications (user_id, opportunity_id, user_intelligence_profile_id, channel, notification_type)
    WHERE channel = 'telegram'
      AND notification_type = 'opportunity_match'
      AND opportunity_id IS NOT NULL
      AND user_intelligence_profile_id IS NOT NULL;

CREATE INDEX notifications_delivery_queue_idx
    ON notifications (channel, notification_type, status, next_attempt_at, created_at)
    WHERE status IN ('pending', 'retry');

CREATE INDEX notifications_delivery_lock_idx
    ON notifications (status, locked_at)
    WHERE status = 'in_progress';

CREATE INDEX notifications_profile_status_idx
    ON notifications (user_intelligence_profile_id, status, created_at DESC)
    WHERE user_intelligence_profile_id IS NOT NULL;

CREATE UNIQUE INDEX google_sheets_journal_notification_uidx
    ON google_sheets_journal (notification_id)
    WHERE notification_id IS NOT NULL;

CREATE OR REPLACE FUNCTION delivery_upsert_telegram_target(
    p_user_id uuid,
    p_chat_id text,
    p_delivery_enabled boolean DEFAULT true,
    p_bot_name text DEFAULT 'Ri assistant'
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
                'bot_name', COALESCE(NULLIF(trim(p_bot_name), ''), 'Ri assistant')
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
                'bot_name', COALESCE(NULLIF(trim(p_bot_name), ''), 'Ri assistant')
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
        COALESCE(v_profile_data #>> '{telegram_delivery,bot_name}', 'Ri assistant');
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
            COALESCE(user_profiles.profile_data #>> '{telegram_delivery,bot_name}', 'Ri assistant') AS bot_name,
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
            COALESCE(user_profiles.profile_data #>> '{telegram_delivery,bot_name}', 'Ri assistant') AS bot_name,
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

CREATE OR REPLACE FUNCTION delivery_mark_notification_sent(
    p_notification_id uuid,
    p_provider_message_id text DEFAULT NULL,
    p_provider_payload jsonb DEFAULT NULL
)
RETURNS TABLE (
    notification_id uuid,
    notification_status text,
    sent_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_notification notifications%ROWTYPE;
    v_sent_at timestamptz := now();
    v_payload jsonb;
BEGIN
    SELECT *
    INTO v_notification
    FROM notifications
    WHERE id = p_notification_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Notification not found: %', p_notification_id;
    END IF;

    v_payload := COALESCE(v_notification.payload, '{}'::jsonb)
        || jsonb_build_object(
            'telegram_delivery_result',
            jsonb_strip_nulls(
                jsonb_build_object(
                    'message_id', NULLIF(trim(p_provider_message_id), ''),
                    'provider_payload', COALESCE(p_provider_payload, '{}'::jsonb),
                    'sent_at', v_sent_at
                )
            )
        );

    UPDATE notifications
    SET
        status = 'sent',
        payload = v_payload,
        error_message = NULL,
        sent_at = v_sent_at,
        locked_at = NULL,
        locked_by = NULL,
        updated_at = now()
    WHERE id = p_notification_id;

    INSERT INTO google_sheets_journal (
        notification_id,
        opportunity_id,
        date,
        source,
        opportunity_type,
        title,
        score,
        status,
        url
    )
    SELECT
        p_notification_id,
        opportunities.id,
        v_sent_at::date,
        sources.name,
        opportunities.opportunity_type,
        opportunities.title,
        opportunity_ai_analysis.opportunity_score,
        opportunity_ai_analysis.recommended_action,
        opportunities.url
    FROM opportunities
    JOIN sources
        ON sources.id = opportunities.source_id
    JOIN notifications
        ON notifications.opportunity_id = opportunities.id
    JOIN opportunity_ai_analysis
        ON opportunity_ai_analysis.opportunity_id = notifications.opportunity_id
       AND opportunity_ai_analysis.user_intelligence_profile_id = notifications.user_intelligence_profile_id
       AND opportunity_ai_analysis.is_current
    WHERE notifications.id = p_notification_id
    ON CONFLICT (notification_id) DO NOTHING;

    RETURN QUERY
    SELECT
        p_notification_id,
        'sent',
        v_sent_at;
END;
$$;

CREATE OR REPLACE FUNCTION delivery_mark_notification_failed(
    p_notification_id uuid,
    p_error_message text,
    p_error_details jsonb DEFAULT NULL,
    p_retry_delay_minutes integer DEFAULT 30,
    p_max_attempts integer DEFAULT 5
)
RETURNS TABLE (
    notification_id uuid,
    notification_status text,
    next_attempt_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_notification notifications%ROWTYPE;
    v_new_status text;
    v_next_attempt_at timestamptz;
    v_error_message text := COALESCE(NULLIF(trim(p_error_message), ''), 'Telegram delivery failed without an explicit error message.');
BEGIN
    SELECT *
    INTO v_notification
    FROM notifications
    WHERE id = p_notification_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Notification not found: %', p_notification_id;
    END IF;

    v_new_status := CASE
        WHEN v_notification.attempt_count >= GREATEST(COALESCE(p_max_attempts, 5), 1) THEN 'failed'
        ELSE 'retry'
    END;

    v_next_attempt_at := CASE
        WHEN v_new_status = 'retry' THEN now() + make_interval(mins => GREATEST(COALESCE(p_retry_delay_minutes, 30), 1))
        ELSE now()
    END;

    UPDATE notifications
    SET
        status = v_new_status,
        error_message = v_error_message,
        next_attempt_at = v_next_attempt_at,
        locked_at = NULL,
        locked_by = NULL,
        updated_at = now()
    WHERE id = p_notification_id;

    INSERT INTO system_logs (
        log_source,
        severity,
        event_type,
        message,
        details,
        correlation_id,
        occurred_at
    )
    VALUES (
        'telegram-delivery-engine',
        CASE
            WHEN v_new_status = 'failed' THEN 'error'
            ELSE 'warning'
        END,
        'notification_delivery_failed',
        format('Telegram delivery failed for notification %s', p_notification_id),
        jsonb_build_object(
            'notification_id', p_notification_id,
            'user_id', v_notification.user_id,
            'opportunity_id', v_notification.opportunity_id,
            'user_intelligence_profile_id', v_notification.user_intelligence_profile_id,
            'attempt_count', v_notification.attempt_count,
            'notification_status', v_new_status,
            'error_message', v_error_message,
            'error_details', COALESCE(p_error_details, '{}'::jsonb)
        ),
        p_notification_id::text,
        now()
    );

    RETURN QUERY
    SELECT
        p_notification_id,
        v_new_status,
        v_next_attempt_at;
END;
$$;

CREATE OR REPLACE FUNCTION delivery_record_notification_action(
    p_notification_id uuid,
    p_action text,
    p_callback_payload jsonb DEFAULT NULL
)
RETURNS TABLE (
    notification_id uuid,
    recorded_action text,
    recorded_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_notification notifications%ROWTYPE;
    v_recorded_at timestamptz := now();
    v_existing_history jsonb;
    v_existing_feedback jsonb;
    v_updated_payload jsonb;
    v_action text := lower(trim(p_action));
BEGIN
    IF v_action NOT IN ('save', 'not_interested', 'later') THEN
        RAISE EXCEPTION 'Unsupported notification action: %', p_action;
    END IF;

    SELECT *
    INTO v_notification
    FROM notifications
    WHERE id = p_notification_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Notification not found: %', p_notification_id;
    END IF;

    v_existing_history := COALESCE(v_notification.payload #> '{telegram_feedback,history}', '[]'::jsonb);
    v_existing_feedback := COALESCE(v_notification.payload -> 'telegram_feedback', '{}'::jsonb);

    v_updated_payload := jsonb_set(
        COALESCE(v_notification.payload, '{}'::jsonb),
        '{telegram_feedback}',
        COALESCE(v_existing_feedback, '{}'::jsonb)
            || jsonb_build_object(
                'last_action', v_action,
                'last_action_at', v_recorded_at,
                'history',
                COALESCE(v_existing_history, '[]'::jsonb)
                    || jsonb_build_array(
                        jsonb_build_object(
                            'action', v_action,
                            'recorded_at', v_recorded_at,
                            'callback_payload', COALESCE(p_callback_payload, '{}'::jsonb)
                        )
                    )
            ),
        true
    );

    UPDATE notifications
    SET
        payload = v_updated_payload,
        updated_at = now()
    WHERE id = p_notification_id;

    INSERT INTO system_logs (
        log_source,
        severity,
        event_type,
        message,
        details,
        correlation_id,
        occurred_at
    )
    VALUES (
        'telegram-delivery-engine',
        'info',
        'notification_action_recorded',
        format('Telegram notification action recorded for %s', p_notification_id),
        jsonb_build_object(
            'notification_id', p_notification_id,
            'action', v_action,
            'callback_payload', COALESCE(p_callback_payload, '{}'::jsonb)
        ),
        p_notification_id::text,
        v_recorded_at
    );

    RETURN QUERY
    SELECT
        p_notification_id,
        v_action,
        v_recorded_at;
END;
$$;

COMMIT;
