BEGIN;

ALTER TABLE notifications
    ADD COLUMN feedback_status text NOT NULL DEFAULT 'awaiting_feedback',
    ADD COLUMN last_user_action text,
    ADD COLUMN last_user_action_at timestamptz,
    ADD COLUMN feedback_result text;

ALTER TABLE notifications
    ADD CONSTRAINT notifications_feedback_status_chk
        CHECK (
            feedback_status IN (
                'awaiting_feedback',
                'saved',
                'deferred',
                'applied',
                'dismissed',
                'completed',
                'won',
                'declined',
                'no_response'
            )
        );

ALTER TABLE google_sheets_journal
    ADD COLUMN user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN user_intelligence_profile_id uuid REFERENCES user_intelligence_profiles(id) ON DELETE SET NULL,
    ADD COLUMN archive_key text,
    ADD COLUMN ai_recommendation text,
    ADD COLUMN user_action text,
    ADD COLUMN result text,
    ADD COLUMN sync_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN last_synced_at timestamptz,
    ADD COLUMN last_sync_error text,
    ADD COLUMN row_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE google_sheets_journal
    ADD CONSTRAINT google_sheets_journal_ai_recommendation_chk
        CHECK (
            ai_recommendation IS NULL
            OR ai_recommendation IN ('apply_now', 'review_manually', 'watchlist', 'skip')
        ),
    ADD CONSTRAINT google_sheets_journal_sync_status_chk
        CHECK (sync_status IN ('pending', 'synced', 'failed', 'skipped')),
    ADD CONSTRAINT google_sheets_journal_row_payload_object_chk
        CHECK (jsonb_typeof(row_payload) = 'object');

UPDATE google_sheets_journal
SET updated_at = created_at
WHERE updated_at IS NULL;

CREATE TABLE feedback_action_catalog (
    action_key text PRIMARY KEY,
    display_name text NOT NULL,
    feedback_signal text NOT NULL,
    feedback_status text NOT NULL,
    opportunity_status text NOT NULL,
    result_code text NOT NULL,
    recommendation_success boolean,
    is_terminal boolean NOT NULL DEFAULT false,
    sort_order integer NOT NULL DEFAULT 100,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT feedback_action_catalog_feedback_signal_chk
        CHECK (feedback_signal IN ('positive', 'neutral', 'negative')),
    CONSTRAINT feedback_action_catalog_feedback_status_chk
        CHECK (
            feedback_status IN (
                'saved',
                'deferred',
                'applied',
                'dismissed',
                'completed',
                'won',
                'declined',
                'no_response'
            )
        ),
    CONSTRAINT feedback_action_catalog_opportunity_status_chk
        CHECK (
            opportunity_status IN (
                'review_pending',
                'shortlisted',
                'applied',
                'rejected',
                'archived'
            )
        ),
    CONSTRAINT feedback_action_catalog_sort_order_chk
        CHECK (sort_order >= 0)
);

INSERT INTO feedback_action_catalog (
    action_key,
    display_name,
    feedback_signal,
    feedback_status,
    opportunity_status,
    result_code,
    recommendation_success,
    is_terminal,
    sort_order
)
VALUES
    ('applied', 'Откликнулся', 'positive', 'applied', 'applied', 'applied', true, false, 10),
    ('saved', 'Сохранить', 'positive', 'saved', 'shortlisted', 'saved', true, false, 20),
    ('later', 'Позже', 'neutral', 'deferred', 'review_pending', 'later', NULL, false, 30),
    ('not_interested', 'Не интересно', 'negative', 'dismissed', 'rejected', 'not_interested', false, true, 40),
    ('already_done', 'Уже выполнено', 'negative', 'completed', 'archived', 'already_done', false, true, 50),
    ('got_project', 'Получил проект', 'positive', 'won', 'archived', 'got_project', true, true, 60),
    ('got_job', 'Получил работу', 'positive', 'won', 'archived', 'got_job', true, true, 70),
    ('rejected', 'Отказ', 'negative', 'declined', 'rejected', 'rejected', false, true, 80),
    ('no_response', 'Нет ответа', 'negative', 'no_response', 'rejected', 'no_response', false, true, 90)
ON CONFLICT (action_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    feedback_signal = EXCLUDED.feedback_signal,
    feedback_status = EXCLUDED.feedback_status,
    opportunity_status = EXCLUDED.opportunity_status,
    result_code = EXCLUDED.result_code,
    recommendation_success = EXCLUDED.recommendation_success,
    is_terminal = EXCLUDED.is_terminal,
    sort_order = EXCLUDED.sort_order,
    updated_at = now();

CREATE TABLE user_feedback_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_intelligence_profile_id uuid REFERENCES user_intelligence_profiles(id) ON DELETE SET NULL,
    notification_id uuid REFERENCES notifications(id) ON DELETE SET NULL,
    opportunity_id uuid REFERENCES opportunities(id) ON DELETE SET NULL,
    feedback_action_key text NOT NULL REFERENCES feedback_action_catalog(action_key) ON DELETE RESTRICT,
    feedback_channel text NOT NULL DEFAULT 'telegram',
    callback_query_id text,
    idempotency_key text NOT NULL,
    ai_recommendation text NOT NULL,
    recommendation_success boolean,
    feedback_signal text NOT NULL,
    result text NOT NULL,
    source_name text NOT NULL,
    source_type text NOT NULL,
    opportunity_type text NOT NULL,
    project_type text NOT NULL,
    title text NOT NULL,
    url text,
    opportunity_score numeric(5, 2),
    technologies text[] NOT NULL DEFAULT ARRAY[]::text[],
    budget_min numeric(14, 2),
    budget_max numeric(14, 2),
    currency char(3),
    event_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_feedback_history_feedback_channel_chk
        CHECK (feedback_channel IN ('telegram', 'email', 'web', 'system', 'manual', 'other')),
    CONSTRAINT user_feedback_history_ai_recommendation_chk
        CHECK (ai_recommendation IN ('apply_now', 'review_manually', 'watchlist', 'skip')),
    CONSTRAINT user_feedback_history_feedback_signal_chk
        CHECK (feedback_signal IN ('positive', 'neutral', 'negative')),
    CONSTRAINT user_feedback_history_project_type_chk
        CHECK (project_type IN ('job', 'freelance', 'project', 'other')),
    CONSTRAINT user_feedback_history_opportunity_score_chk
        CHECK (opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 100),
    CONSTRAINT user_feedback_history_currency_chk
        CHECK (currency IS NULL OR currency::text ~ '^[A-Z]{3}$'),
    CONSTRAINT user_feedback_history_event_payload_object_chk
        CHECK (jsonb_typeof(event_payload) = 'object'),
    CONSTRAINT user_feedback_history_idempotency_key_key UNIQUE (idempotency_key)
);

CREATE TABLE learning_feedback_dataset (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_history_id uuid NOT NULL REFERENCES user_feedback_history(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_intelligence_profile_id uuid REFERENCES user_intelligence_profiles(id) ON DELETE SET NULL,
    notification_id uuid REFERENCES notifications(id) ON DELETE SET NULL,
    opportunity_id uuid REFERENCES opportunities(id) ON DELETE SET NULL,
    ai_provider text,
    ai_model_name text,
    prompt_version text,
    ai_recommendation text NOT NULL,
    recommendation_success boolean,
    feedback_signal text NOT NULL,
    user_action text NOT NULL,
    result text NOT NULL,
    source_name text NOT NULL,
    source_type text NOT NULL,
    opportunity_type text NOT NULL,
    project_type text NOT NULL,
    technologies text[] NOT NULL DEFAULT ARRAY[]::text[],
    opportunity_score numeric(5, 2),
    fit_score numeric(5, 2),
    difficulty_score numeric(5, 2),
    income_potential_score numeric(5, 2),
    probability_to_win_score numeric(5, 2),
    urgency_score numeric(5, 2),
    skills_match_score numeric(5, 2),
    budget_min numeric(14, 2),
    budget_max numeric(14, 2),
    currency char(3),
    opportunity_title text NOT NULL,
    opportunity_url text,
    feature_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    captured_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT learning_feedback_dataset_feedback_history_id_key UNIQUE (feedback_history_id),
    CONSTRAINT learning_feedback_dataset_ai_recommendation_chk
        CHECK (ai_recommendation IN ('apply_now', 'review_manually', 'watchlist', 'skip')),
    CONSTRAINT learning_feedback_dataset_feedback_signal_chk
        CHECK (feedback_signal IN ('positive', 'neutral', 'negative')),
    CONSTRAINT learning_feedback_dataset_project_type_chk
        CHECK (project_type IN ('job', 'freelance', 'project', 'other')),
    CONSTRAINT learning_feedback_dataset_opportunity_score_chk
        CHECK (opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_fit_score_chk
        CHECK (fit_score IS NULL OR fit_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_difficulty_score_chk
        CHECK (difficulty_score IS NULL OR difficulty_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_income_potential_score_chk
        CHECK (income_potential_score IS NULL OR income_potential_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_probability_to_win_score_chk
        CHECK (probability_to_win_score IS NULL OR probability_to_win_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_urgency_score_chk
        CHECK (urgency_score IS NULL OR urgency_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_skills_match_score_chk
        CHECK (skills_match_score IS NULL OR skills_match_score BETWEEN 0 AND 100),
    CONSTRAINT learning_feedback_dataset_currency_chk
        CHECK (currency IS NULL OR currency::text ~ '^[A-Z]{3}$'),
    CONSTRAINT learning_feedback_dataset_feature_payload_object_chk
        CHECK (jsonb_typeof(feature_payload) = 'object')
);

CREATE UNIQUE INDEX google_sheets_journal_archive_key_uidx
    ON google_sheets_journal (archive_key)
    WHERE archive_key IS NOT NULL;

CREATE INDEX google_sheets_journal_sync_status_idx
    ON google_sheets_journal (sync_status, created_at DESC)
    WHERE archive_key IS NOT NULL;

CREATE INDEX notifications_feedback_status_idx
    ON notifications (feedback_status, last_user_action_at DESC)
    WHERE last_user_action_at IS NOT NULL;

CREATE UNIQUE INDEX user_feedback_history_callback_query_uidx
    ON user_feedback_history (callback_query_id)
    WHERE callback_query_id IS NOT NULL;

CREATE INDEX user_feedback_history_user_recorded_idx
    ON user_feedback_history (user_id, recorded_at DESC);

CREATE INDEX user_feedback_history_profile_action_idx
    ON user_feedback_history (user_intelligence_profile_id, feedback_action_key, recorded_at DESC)
    WHERE user_intelligence_profile_id IS NOT NULL;

CREATE INDEX learning_feedback_dataset_success_source_idx
    ON learning_feedback_dataset (recommendation_success, source_name, captured_at DESC);

CREATE INDEX learning_feedback_dataset_project_type_idx
    ON learning_feedback_dataset (project_type, captured_at DESC);

CREATE INDEX learning_feedback_dataset_technologies_gin_idx
    ON learning_feedback_dataset USING gin (technologies);

CREATE TRIGGER feedback_action_catalog_set_updated_at
    BEFORE UPDATE ON feedback_action_catalog
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

CREATE TRIGGER google_sheets_journal_set_updated_at
    BEFORE UPDATE ON google_sheets_journal
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

UPDATE google_sheets_journal
SET
    user_id = notifications.user_id,
    user_intelligence_profile_id = notifications.user_intelligence_profile_id,
    archive_key = CASE
        WHEN opportunity_ai_analysis.recommended_action IN ('apply_now', 'review_manually') THEN concat_ws(
            ':',
            'feedback-archive',
            notifications.user_id::text,
            notifications.user_intelligence_profile_id::text,
            notifications.opportunity_id::text
        )
        ELSE COALESCE(google_sheets_journal.archive_key, concat_ws(':', 'delivery-journal', google_sheets_journal.id::text))
    END,
    ai_recommendation = COALESCE(opportunity_ai_analysis.recommended_action, google_sheets_journal.status),
    user_action = COALESCE(google_sheets_journal.user_action, 'sent_to_telegram'),
    result = COALESCE(google_sheets_journal.result, 'delivered'),
    sync_status = CASE
        WHEN opportunity_ai_analysis.recommended_action IN ('apply_now', 'review_manually') THEN 'pending'
        ELSE 'skipped'
    END,
    row_payload = COALESCE(google_sheets_journal.row_payload, '{}'::jsonb)
        || jsonb_build_object(
            'legacy_delivery_journal', true,
            'notification_id', google_sheets_journal.notification_id,
            'status', google_sheets_journal.status
        ),
    updated_at = now()
FROM notifications
LEFT JOIN opportunity_ai_analysis
    ON opportunity_ai_analysis.opportunity_id = notifications.opportunity_id
   AND opportunity_ai_analysis.user_intelligence_profile_id = notifications.user_intelligence_profile_id
   AND opportunity_ai_analysis.is_current
WHERE google_sheets_journal.notification_id = notifications.id;

UPDATE google_sheets_journal
SET
    archive_key = COALESCE(archive_key, concat_ws(':', 'delivery-journal', id::text)),
    ai_recommendation = COALESCE(ai_recommendation, status),
    user_action = COALESCE(user_action, 'sent_to_telegram'),
    result = COALESCE(result, 'delivered'),
    sync_status = COALESCE(sync_status, 'skipped'),
    row_payload = COALESCE(row_payload, '{}'::jsonb)
        || jsonb_build_object(
            'legacy_delivery_journal', true,
            'notification_id', notification_id,
            'status', status
        ),
    updated_at = now()
WHERE archive_key IS NULL
   OR ai_recommendation IS NULL
   OR user_action IS NULL
   OR result IS NULL;

CREATE OR REPLACE FUNCTION feedback_normalize_project_type(
    p_opportunity_type text
)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE lower(trim(COALESCE(p_opportunity_type, '')))
        WHEN 'vacancy' THEN 'job'
        WHEN 'part_time' THEN 'job'
        WHEN 'freelance_order' THEN 'freelance'
        WHEN 'one_time_task' THEN 'freelance'
        WHEN 'project' THEN 'project'
        WHEN 'automation_request' THEN 'project'
        WHEN 'n8n_task' THEN 'project'
        WHEN 'telegram_bot_task' THEN 'project'
        WHEN 'openai_task' THEN 'project'
        WHEN 'business_automation_task' THEN 'project'
        WHEN '' THEN 'other'
        ELSE 'other'
    END;
$$;

CREATE OR REPLACE FUNCTION feedback_extract_matched_technologies(
    p_candidate_technologies text[],
    p_search_text text
)
RETURNS text[]
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT COALESCE(
        array_agg(DISTINCT normalized.tech ORDER BY normalized.tech),
        ARRAY[]::text[]
    )
    FROM (
        SELECT lower(trim(candidate)) AS tech
        FROM unnest(COALESCE(p_candidate_technologies, ARRAY[]::text[])) AS candidate
        WHERE trim(COALESCE(candidate, '')) <> ''
          AND strpos(lower(COALESCE(p_search_text, '')), lower(trim(candidate))) > 0
    ) AS normalized;
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
        feedback_status = 'awaiting_feedback',
        updated_at = now()
    WHERE id = p_notification_id;

    RETURN QUERY
    SELECT
        p_notification_id,
        'sent',
        v_sent_at;
END;
$$;

CREATE OR REPLACE FUNCTION feedback_record_notification_action(
    p_notification_id uuid,
    p_action text,
    p_callback_payload jsonb DEFAULT NULL
)
RETURNS TABLE (
    notification_id uuid,
    feedback_history_id uuid,
    learning_dataset_id uuid,
    recorded_action text,
    recorded_at timestamptz,
    ai_recommendation text,
    archive_required boolean,
    archive_key text,
    archive_date date,
    archive_source text,
    archive_opportunity_type text,
    archive_title text,
    archive_score numeric,
    archive_user_action text,
    archive_result text,
    archive_url text,
    sync_status text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_notification notifications%ROWTYPE;
    v_opportunity opportunities%ROWTYPE;
    v_analysis opportunity_ai_analysis%ROWTYPE;
    v_profile user_intelligence_profiles%ROWTYPE;
    v_action_config feedback_action_catalog%ROWTYPE;
    v_recorded_at timestamptz := now();
    v_action text := lower(trim(p_action));
    v_callback_query_id text := NULLIF(trim(COALESCE(
        p_callback_payload #>> '{callback_query,id}',
        p_callback_payload #>> '{callbackQuery,id}',
        ''
    )), '');
    v_idempotency_key text;
    v_project_type text;
    v_matched_technologies text[];
    v_feedback_history_id uuid;
    v_learning_dataset_id uuid;
    v_archive_required boolean;
    v_archive_key text;
    v_existing_feedback_history jsonb;
    v_existing_feedback jsonb;
    v_updated_payload jsonb;
    v_feature_payload jsonb;
    v_search_text text;
BEGIN
    SELECT *
    INTO v_action_config
    FROM feedback_action_catalog
    WHERE action_key = v_action;

    IF NOT FOUND THEN
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

    SELECT *
    INTO v_opportunity
    FROM opportunities
    WHERE id = v_notification.opportunity_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Opportunity not found for notification: %', p_notification_id;
    END IF;

    SELECT *
    INTO v_analysis
    FROM opportunity_ai_analysis
    WHERE opportunity_id = v_notification.opportunity_id
      AND user_intelligence_profile_id = v_notification.user_intelligence_profile_id
      AND is_current
    ORDER BY analyzed_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Current AI analysis not found for notification: %', p_notification_id;
    END IF;

    SELECT *
    INTO v_profile
    FROM user_intelligence_profiles
    WHERE id = v_notification.user_intelligence_profile_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User intelligence profile not found for notification: %', p_notification_id;
    END IF;

    v_idempotency_key := COALESCE(
        'telegram_callback:' || v_callback_query_id,
        concat_ws(':', 'telegram_action', p_notification_id::text, v_action)
    );

    v_archive_required := v_analysis.recommended_action IN ('apply_now', 'review_manually');
    v_archive_key := CASE
        WHEN v_archive_required THEN concat_ws(
            ':',
            'feedback-archive',
            v_notification.user_id::text,
            v_notification.user_intelligence_profile_id::text,
            v_notification.opportunity_id::text
        )
        ELSE NULL
    END;

    v_project_type := feedback_normalize_project_type(v_opportunity.opportunity_type);
    v_search_text := lower(
        concat_ws(
            ' ',
            COALESCE(v_opportunity.title, ''),
            COALESCE(v_opportunity.description, ''),
            COALESCE(v_opportunity.raw_text, ''),
            COALESCE(v_opportunity.company_name, '')
        )
    );
    v_matched_technologies := feedback_extract_matched_technologies(
        COALESCE(v_profile.technology_stack, ARRAY[]::text[]) || COALESCE(v_profile.core_skills, ARRAY[]::text[]),
        v_search_text
    );

    INSERT INTO user_feedback_history (
        user_id,
        user_intelligence_profile_id,
        notification_id,
        opportunity_id,
        feedback_action_key,
        feedback_channel,
        callback_query_id,
        idempotency_key,
        ai_recommendation,
        recommendation_success,
        feedback_signal,
        result,
        source_name,
        source_type,
        opportunity_type,
        project_type,
        title,
        url,
        opportunity_score,
        technologies,
        budget_min,
        budget_max,
        currency,
        event_payload,
        recorded_at
    )
    SELECT
        v_notification.user_id,
        v_notification.user_intelligence_profile_id,
        v_notification.id,
        v_notification.opportunity_id,
        v_action,
        'telegram',
        v_callback_query_id,
        v_idempotency_key,
        v_analysis.recommended_action,
        v_action_config.recommendation_success,
        v_action_config.feedback_signal,
        v_action_config.result_code,
        sources.name,
        v_opportunity.source_type,
        v_opportunity.opportunity_type,
        v_project_type,
        v_opportunity.title,
        v_opportunity.url,
        v_analysis.opportunity_score,
        COALESCE(v_matched_technologies, ARRAY[]::text[]),
        v_opportunity.budget_min,
        v_opportunity.budget_max,
        v_opportunity.currency,
        jsonb_strip_nulls(
            jsonb_build_object(
                'callback_payload', COALESCE(p_callback_payload, '{}'::jsonb),
                'notification_payload', COALESCE(v_notification.payload, '{}'::jsonb),
                'analysis_id', v_analysis.id
            )
        ),
        v_recorded_at
    FROM sources
    WHERE sources.id = v_opportunity.source_id
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING id
    INTO v_feedback_history_id;

    IF v_feedback_history_id IS NULL THEN
        RETURN QUERY
        SELECT
            v_notification.id,
            existing_history.id,
            existing_dataset.id,
            existing_history.feedback_action_key,
            existing_history.recorded_at,
            existing_history.ai_recommendation,
            existing_history.ai_recommendation IN ('apply_now', 'review_manually'),
            existing_journal.archive_key,
            existing_journal.date,
            existing_journal.source,
            existing_journal.opportunity_type,
            existing_journal.title,
            existing_journal.score,
            existing_journal.user_action,
            existing_journal.result,
            existing_journal.url,
            existing_journal.sync_status
        FROM user_feedback_history AS existing_history
        LEFT JOIN learning_feedback_dataset AS existing_dataset
            ON existing_dataset.feedback_history_id = existing_history.id
        LEFT JOIN google_sheets_journal AS existing_journal
            ON existing_journal.archive_key = concat_ws(
                ':',
                'feedback-archive',
                existing_history.user_id::text,
                COALESCE(existing_history.user_intelligence_profile_id::text, 'unscoped'),
                COALESCE(existing_history.opportunity_id::text, 'unlinked')
            )
        WHERE existing_history.idempotency_key = v_idempotency_key;
        RETURN;
    END IF;

    v_existing_feedback_history := COALESCE(v_notification.payload #> '{feedback_engine,history}', '[]'::jsonb);
    v_existing_feedback := COALESCE(v_notification.payload -> 'feedback_engine', '{}'::jsonb);

    v_updated_payload := jsonb_set(
        COALESCE(v_notification.payload, '{}'::jsonb),
        '{feedback_engine}',
        COALESCE(v_existing_feedback, '{}'::jsonb)
            || jsonb_build_object(
                'last_action', v_action,
                'last_action_at', v_recorded_at,
                'last_result', v_action_config.result_code,
                'callback_query_id', v_callback_query_id,
                'history',
                COALESCE(v_existing_feedback_history, '[]'::jsonb)
                    || jsonb_build_array(
                        jsonb_strip_nulls(
                            jsonb_build_object(
                                'idempotency_key', v_idempotency_key,
                                'action', v_action,
                                'feedback_status', v_action_config.feedback_status,
                                'result', v_action_config.result_code,
                                'recorded_at', v_recorded_at,
                                'callback_query_id', v_callback_query_id
                            )
                        )
                    )
            ),
        true
    );

    UPDATE notifications
    SET
        payload = v_updated_payload,
        feedback_status = v_action_config.feedback_status,
        last_user_action = v_action,
        last_user_action_at = v_recorded_at,
        feedback_result = v_action_config.result_code,
        updated_at = now()
    WHERE id = v_notification.id;

    UPDATE opportunities
    SET
        status = v_action_config.opportunity_status,
        updated_at = now()
    WHERE id = v_notification.opportunity_id;

    v_feature_payload := jsonb_strip_nulls(
        jsonb_build_object(
            'analysis_snapshot',
            jsonb_build_object(
                'llm_provider', v_analysis.llm_provider,
                'model_name', v_analysis.model_name,
                'prompt_version', v_analysis.prompt_version,
                'fit_score', v_analysis.fit_score,
                'opportunity_score', v_analysis.opportunity_score,
                'difficulty_score', v_analysis.difficulty_score,
                'income_potential_score', v_analysis.income_potential_score,
                'probability_to_win_score', v_analysis.probability_to_win_score,
                'urgency_score', v_analysis.urgency_score,
                'skills_match_score', v_analysis.skills_match_score,
                'decision_confidence_score', v_analysis.decision_confidence_score,
                'recommended_action', v_analysis.recommended_action,
                'input_snapshot', v_analysis.input_snapshot,
                'analysis_payload', v_analysis.analysis_payload
            ),
            'profile_snapshot',
            jsonb_build_object(
                'profile_slug', v_profile.profile_slug,
                'core_skills', to_jsonb(v_profile.core_skills),
                'technology_stack', to_jsonb(v_profile.technology_stack),
                'preferred_project_types', to_jsonb(v_profile.preferred_project_types),
                'undesirable_project_types', to_jsonb(v_profile.undesirable_project_types),
                'minimum_project_budget', v_profile.minimum_project_budget,
                'preferred_currency', v_profile.preferred_currency,
                'english_level', v_profile.english_level,
                'experience_level', v_profile.experience_level,
                'include_keywords', to_jsonb(v_profile.include_keywords),
                'exclude_keywords', to_jsonb(v_profile.exclude_keywords),
                'priority_directions', to_jsonb(v_profile.priority_directions),
                'scoring_policy', v_profile.scoring_policy
            ),
            'opportunity_snapshot',
            jsonb_build_object(
                'title', v_opportunity.title,
                'description', v_opportunity.description,
                'raw_text', v_opportunity.raw_text,
                'url', v_opportunity.url,
                'company_name', v_opportunity.company_name,
                'opportunity_type', v_opportunity.opportunity_type,
                'project_type', v_project_type,
                'source_type', v_opportunity.source_type,
                'location', v_opportunity.location,
                'remote_type', v_opportunity.remote_type,
                'budget_min', v_opportunity.budget_min,
                'budget_max', v_opportunity.budget_max,
                'currency', v_opportunity.currency,
                'matched_technologies', to_jsonb(COALESCE(v_matched_technologies, ARRAY[]::text[]))
            ),
            'feedback_payload', COALESCE(p_callback_payload, '{}'::jsonb)
        )
    );

    INSERT INTO learning_feedback_dataset (
        feedback_history_id,
        user_id,
        user_intelligence_profile_id,
        notification_id,
        opportunity_id,
        ai_provider,
        ai_model_name,
        prompt_version,
        ai_recommendation,
        recommendation_success,
        feedback_signal,
        user_action,
        result,
        source_name,
        source_type,
        opportunity_type,
        project_type,
        technologies,
        opportunity_score,
        fit_score,
        difficulty_score,
        income_potential_score,
        probability_to_win_score,
        urgency_score,
        skills_match_score,
        budget_min,
        budget_max,
        currency,
        opportunity_title,
        opportunity_url,
        feature_payload,
        captured_at
    )
    SELECT
        v_feedback_history_id,
        v_notification.user_id,
        v_notification.user_intelligence_profile_id,
        v_notification.id,
        v_notification.opportunity_id,
        v_analysis.llm_provider,
        v_analysis.model_name,
        v_analysis.prompt_version,
        v_analysis.recommended_action,
        v_action_config.recommendation_success,
        v_action_config.feedback_signal,
        v_action,
        v_action_config.result_code,
        sources.name,
        v_opportunity.source_type,
        v_opportunity.opportunity_type,
        v_project_type,
        COALESCE(v_matched_technologies, ARRAY[]::text[]),
        v_analysis.opportunity_score,
        v_analysis.fit_score,
        v_analysis.difficulty_score,
        v_analysis.income_potential_score,
        v_analysis.probability_to_win_score,
        v_analysis.urgency_score,
        v_analysis.skills_match_score,
        v_opportunity.budget_min,
        v_opportunity.budget_max,
        v_opportunity.currency,
        v_opportunity.title,
        v_opportunity.url,
        v_feature_payload,
        v_recorded_at
    FROM sources
    WHERE sources.id = v_opportunity.source_id
    RETURNING id
    INTO v_learning_dataset_id;

    IF v_archive_required THEN
        INSERT INTO google_sheets_journal (
            notification_id,
            opportunity_id,
            user_id,
            user_intelligence_profile_id,
            archive_key,
            date,
            source,
            opportunity_type,
            title,
            score,
            status,
            url,
            ai_recommendation,
            user_action,
            result,
            sync_status,
            last_synced_at,
            last_sync_error,
            row_payload,
            updated_at
        )
        SELECT
            v_notification.id,
            v_notification.opportunity_id,
            v_notification.user_id,
            v_notification.user_intelligence_profile_id,
            v_archive_key,
            v_recorded_at::date,
            sources.name,
            v_project_type,
            v_opportunity.title,
            v_analysis.opportunity_score,
            v_analysis.recommended_action,
            v_opportunity.url,
            v_analysis.recommended_action,
            v_action,
            v_action_config.result_code,
            'pending',
            NULL,
            NULL,
            jsonb_strip_nulls(
                jsonb_build_object(
                    'feedback_history_id', v_feedback_history_id,
                    'learning_dataset_id', v_learning_dataset_id,
                    'feedback_signal', v_action_config.feedback_signal,
                    'recommendation_success', v_action_config.recommendation_success,
                    'project_type', v_project_type,
                    'technologies', to_jsonb(COALESCE(v_matched_technologies, ARRAY[]::text[])),
                    'budget_min', v_opportunity.budget_min,
                    'budget_max', v_opportunity.budget_max,
                    'currency', v_opportunity.currency
                )
            ),
            now()
        FROM sources
        WHERE sources.id = v_opportunity.source_id
        ON CONFLICT (archive_key) DO UPDATE SET
            notification_id = EXCLUDED.notification_id,
            opportunity_id = EXCLUDED.opportunity_id,
            user_id = EXCLUDED.user_id,
            user_intelligence_profile_id = EXCLUDED.user_intelligence_profile_id,
            date = EXCLUDED.date,
            source = EXCLUDED.source,
            opportunity_type = EXCLUDED.opportunity_type,
            title = EXCLUDED.title,
            score = EXCLUDED.score,
            status = EXCLUDED.status,
            url = EXCLUDED.url,
            ai_recommendation = EXCLUDED.ai_recommendation,
            user_action = EXCLUDED.user_action,
            result = EXCLUDED.result,
            sync_status = 'pending',
            last_synced_at = NULL,
            last_sync_error = NULL,
            row_payload = EXCLUDED.row_payload,
            updated_at = now();
    END IF;

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
        'feedback-learning-engine',
        'info',
        'feedback_action_recorded',
        format('Feedback action %s recorded for notification %s', v_action, p_notification_id),
        jsonb_build_object(
            'notification_id', p_notification_id,
            'feedback_history_id', v_feedback_history_id,
            'learning_dataset_id', v_learning_dataset_id,
            'action', v_action,
            'archive_required', v_archive_required,
            'archive_key', v_archive_key
        ),
        v_idempotency_key,
        v_recorded_at
    );

    RETURN QUERY
    SELECT
        v_notification.id,
        v_feedback_history_id,
        v_learning_dataset_id,
        v_action,
        v_recorded_at,
        v_analysis.recommended_action,
        v_archive_required,
        v_archive_key,
        CASE WHEN v_archive_required THEN v_recorded_at::date ELSE NULL END,
        CASE WHEN v_archive_required THEN sources.name ELSE NULL END,
        CASE WHEN v_archive_required THEN v_project_type ELSE NULL END,
        CASE WHEN v_archive_required THEN v_opportunity.title ELSE NULL END,
        CASE WHEN v_archive_required THEN v_analysis.opportunity_score ELSE NULL END,
        CASE WHEN v_archive_required THEN v_action ELSE NULL END,
        CASE WHEN v_archive_required THEN v_action_config.result_code ELSE NULL END,
        CASE WHEN v_archive_required THEN v_opportunity.url ELSE NULL END,
        CASE WHEN v_archive_required THEN 'pending' ELSE 'skipped' END
    FROM sources
    WHERE sources.id = v_opportunity.source_id;
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
BEGIN
    RETURN QUERY
    SELECT
        feedback_notification.notification_id,
        feedback_notification.recorded_action,
        feedback_notification.recorded_at
    FROM feedback_record_notification_action(
        p_notification_id,
        p_action,
        p_callback_payload
    ) AS feedback_notification;
END;
$$;

CREATE OR REPLACE FUNCTION feedback_mark_google_sheet_archive_synced(
    p_archive_key text,
    p_provider_payload jsonb DEFAULT NULL
)
RETURNS TABLE (
    archive_key text,
    sync_status text,
    synced_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_archive_key text := NULLIF(trim(p_archive_key), '');
    v_synced_at timestamptz := now();
BEGIN
    IF v_archive_key IS NULL THEN
        RAISE EXCEPTION 'Archive key is required.';
    END IF;

    UPDATE google_sheets_journal
    SET
        sync_status = 'synced',
        last_synced_at = v_synced_at,
        last_sync_error = NULL,
        row_payload = COALESCE(row_payload, '{}'::jsonb)
            || jsonb_build_object(
                'google_sheets_sync',
                jsonb_strip_nulls(
                    jsonb_build_object(
                        'last_synced_at', v_synced_at,
                        'provider_payload', COALESCE(p_provider_payload, '{}'::jsonb)
                    )
                )
            ),
        updated_at = now()
    WHERE google_sheets_journal.archive_key = v_archive_key;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Google Sheets archive row not found: %', v_archive_key;
    END IF;

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
        'feedback-learning-engine',
        'info',
        'google_sheets_archive_synced',
        format('Google Sheets archive synced for %s', v_archive_key),
        jsonb_build_object(
            'archive_key', v_archive_key,
            'provider_payload', COALESCE(p_provider_payload, '{}'::jsonb)
        ),
        v_archive_key,
        v_synced_at
    );

    RETURN QUERY
    SELECT
        v_archive_key,
        'synced',
        v_synced_at;
END;
$$;

CREATE OR REPLACE FUNCTION feedback_mark_google_sheet_archive_failed(
    p_archive_key text,
    p_error_message text,
    p_error_details jsonb DEFAULT NULL
)
RETURNS TABLE (
    archive_key text,
    sync_status text,
    failed_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_archive_key text := NULLIF(trim(p_archive_key), '');
    v_failed_at timestamptz := now();
    v_error_message text := COALESCE(NULLIF(trim(p_error_message), ''), 'Google Sheets archive sync failed.');
BEGIN
    IF v_archive_key IS NULL THEN
        RAISE EXCEPTION 'Archive key is required.';
    END IF;

    UPDATE google_sheets_journal
    SET
        sync_status = 'failed',
        last_sync_error = v_error_message,
        row_payload = COALESCE(row_payload, '{}'::jsonb)
            || jsonb_build_object(
                'google_sheets_sync_error',
                jsonb_strip_nulls(
                    jsonb_build_object(
                        'failed_at', v_failed_at,
                        'error_message', v_error_message,
                        'error_details', COALESCE(p_error_details, '{}'::jsonb)
                    )
                )
            ),
        updated_at = now()
    WHERE google_sheets_journal.archive_key = v_archive_key;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Google Sheets archive row not found: %', v_archive_key;
    END IF;

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
        'feedback-learning-engine',
        'warning',
        'google_sheets_archive_failed',
        format('Google Sheets archive sync failed for %s', v_archive_key),
        jsonb_build_object(
            'archive_key', v_archive_key,
            'error_message', v_error_message,
            'error_details', COALESCE(p_error_details, '{}'::jsonb)
        ),
        v_archive_key,
        v_failed_at
    );

    RETURN QUERY
    SELECT
        v_archive_key,
        'failed',
        v_failed_at;
END;
$$;

CREATE OR REPLACE FUNCTION feedback_purge_expired_working_memory(
    p_retention_days integer DEFAULT 60
)
RETURNS TABLE (
    retention_days integer,
    cutoff_at timestamptz,
    deleted_notifications integer,
    deleted_opportunities integer,
    deleted_opportunity_ai_analysis integer,
    deleted_opportunity_scores integer,
    deleted_source_run_logs integer,
    deleted_system_logs integer
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_retention_days integer := GREATEST(COALESCE(p_retention_days, 60), 1);
    v_cutoff_at timestamptz := now() - make_interval(days => v_retention_days);
    v_deleted_notifications integer := 0;
    v_deleted_opportunities integer := 0;
    v_deleted_opportunity_ai_analysis integer := 0;
    v_deleted_opportunity_scores integer := 0;
    v_deleted_source_run_logs integer := 0;
    v_deleted_system_logs integer := 0;
BEGIN
    WITH deleted_rows AS (
        DELETE FROM notifications
        WHERE COALESCE(last_user_action_at, sent_at, created_at) < v_cutoff_at
        RETURNING 1
    )
    SELECT COUNT(*)
    INTO v_deleted_notifications
    FROM deleted_rows;

    WITH deleted_rows AS (
        DELETE FROM opportunity_ai_analysis
        WHERE COALESCE(analyzed_at, created_at) < v_cutoff_at
        RETURNING 1
    )
    SELECT COUNT(*)
    INTO v_deleted_opportunity_ai_analysis
    FROM deleted_rows;

    WITH deleted_rows AS (
        DELETE FROM opportunity_scores
        WHERE COALESCE(calculated_at, created_at) < v_cutoff_at
        RETURNING 1
    )
    SELECT COUNT(*)
    INTO v_deleted_opportunity_scores
    FROM deleted_rows;

    WITH deleted_rows AS (
        DELETE FROM source_run_logs
        WHERE COALESCE(run_finished_at, run_started_at, created_at) < v_cutoff_at
        RETURNING 1
    )
    SELECT COUNT(*)
    INTO v_deleted_source_run_logs
    FROM deleted_rows;

    WITH deleted_rows AS (
        DELETE FROM system_logs
        WHERE COALESCE(occurred_at, created_at) < v_cutoff_at
        RETURNING 1
    )
    SELECT COUNT(*)
    INTO v_deleted_system_logs
    FROM deleted_rows;

    WITH deleted_rows AS (
        DELETE FROM opportunities
        WHERE COALESCE(collected_at, created_at) < v_cutoff_at
        RETURNING 1
    )
    SELECT COUNT(*)
    INTO v_deleted_opportunities
    FROM deleted_rows;

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
        'feedback-learning-engine',
        'info',
        'working_memory_purged',
        format('Expired working memory purged with retention window %s days', v_retention_days),
        jsonb_build_object(
            'retention_days', v_retention_days,
            'cutoff_at', v_cutoff_at,
            'deleted_notifications', v_deleted_notifications,
            'deleted_opportunities', v_deleted_opportunities,
            'deleted_opportunity_ai_analysis', v_deleted_opportunity_ai_analysis,
            'deleted_opportunity_scores', v_deleted_opportunity_scores,
            'deleted_source_run_logs', v_deleted_source_run_logs,
            'deleted_system_logs', v_deleted_system_logs
        ),
        concat_ws(':', 'working-memory-retention', v_retention_days::text, to_char(now(), 'YYYYMMDDHH24MISS')),
        now()
    );

    RETURN QUERY
    SELECT
        v_retention_days,
        v_cutoff_at,
        v_deleted_notifications,
        v_deleted_opportunities,
        v_deleted_opportunity_ai_analysis,
        v_deleted_opportunity_scores,
        v_deleted_source_run_logs,
        v_deleted_system_logs;
END;
$$;

COMMIT;
