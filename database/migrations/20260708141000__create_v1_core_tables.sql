BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    display_name text,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_status_chk
        CHECK (status IN ('active', 'inactive', 'archived'))
);

CREATE TABLE user_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    headline text,
    summary text,
    location text,
    remote_preference text NOT NULL DEFAULT 'flexible',
    profile_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_profiles_user_id_key UNIQUE (user_id),
    CONSTRAINT user_profiles_remote_preference_chk
        CHECK (remote_preference IN ('remote', 'hybrid', 'onsite', 'flexible')),
    CONSTRAINT user_profiles_profile_data_object_chk
        CHECK (jsonb_typeof(profile_data) = 'object')
);

CREATE TABLE sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    type text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    config_reference text,
    last_success_at timestamptz,
    last_error_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sources_name_type_key UNIQUE (name, type),
    CONSTRAINT sources_type_chk
        CHECK (type IN ('job_board', 'freelance_marketplace', 'telegram', 'website', 'referral', 'manual', 'api', 'other'))
);

CREATE TABLE opportunities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    external_id text,
    title text NOT NULL,
    description text,
    raw_text text,
    url text,
    company_name text,
    opportunity_type text NOT NULL,
    source_type text NOT NULL,
    location text,
    remote_type text NOT NULL DEFAULT 'unknown',
    budget_min numeric(14, 2),
    budget_max numeric(14, 2),
    currency char(3),
    published_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'new',
    duplicate_hash char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT opportunities_opportunity_type_chk
        CHECK (
            opportunity_type IN (
                'vacancy',
                'freelance_order',
                'one_time_task',
                'project',
                'part_time',
                'telegram_request',
                'automation_request',
                'n8n_task',
                'telegram_bot_task',
                'openai_task',
                'business_automation_task',
                'other'
            )
        ),
    CONSTRAINT opportunities_source_type_chk
        CHECK (source_type IN ('job_board', 'freelance_marketplace', 'telegram', 'website', 'referral', 'manual', 'api', 'other')),
    CONSTRAINT opportunities_remote_type_chk
        CHECK (remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')),
    CONSTRAINT opportunities_budget_range_chk
        CHECK (budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max),
    CONSTRAINT opportunities_currency_chk
        CHECK (currency IS NULL OR currency::text ~ '^[A-Z]{3}$'),
    CONSTRAINT opportunities_status_chk
        CHECK (status IN ('new', 'review_pending', 'analyzed', 'shortlisted', 'applied', 'rejected', 'archived')),
    CONSTRAINT opportunities_duplicate_hash_chk
        CHECK (duplicate_hash ~ '^[0-9a-f]{64}$')
);

CREATE TABLE opportunity_ai_analysis (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id uuid NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    summary text NOT NULL,
    fit_score numeric(5, 2),
    opportunity_score numeric(5, 2),
    difficulty_score numeric(5, 2),
    income_potential_score numeric(5, 2),
    probability_to_win_score numeric(5, 2),
    reasons_to_apply jsonb NOT NULL DEFAULT '[]'::jsonb,
    risks jsonb NOT NULL DEFAULT '[]'::jsonb,
    recommended_action text NOT NULL,
    model_name text NOT NULL,
    is_current boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT opportunity_ai_analysis_fit_score_chk
        CHECK (fit_score IS NULL OR fit_score BETWEEN 0 AND 100),
    CONSTRAINT opportunity_ai_analysis_opportunity_score_chk
        CHECK (opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 100),
    CONSTRAINT opportunity_ai_analysis_difficulty_score_chk
        CHECK (difficulty_score IS NULL OR difficulty_score BETWEEN 0 AND 100),
    CONSTRAINT opportunity_ai_analysis_income_potential_score_chk
        CHECK (income_potential_score IS NULL OR income_potential_score BETWEEN 0 AND 100),
    CONSTRAINT opportunity_ai_analysis_probability_to_win_score_chk
        CHECK (probability_to_win_score IS NULL OR probability_to_win_score BETWEEN 0 AND 100),
    CONSTRAINT opportunity_ai_analysis_recommended_action_chk
        CHECK (recommended_action IN ('apply_now', 'review_manually', 'watchlist', 'skip')),
    CONSTRAINT opportunity_ai_analysis_reasons_to_apply_array_chk
        CHECK (jsonb_typeof(reasons_to_apply) = 'array'),
    CONSTRAINT opportunity_ai_analysis_risks_array_chk
        CHECK (jsonb_typeof(risks) = 'array')
);

CREATE TABLE opportunity_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id uuid NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    score_type text NOT NULL,
    score_value numeric(5, 2) NOT NULL,
    score_source text NOT NULL DEFAULT 'ai_analysis',
    scoring_version text NOT NULL DEFAULT 'v1',
    is_current boolean NOT NULL DEFAULT true,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT opportunity_scores_score_type_chk
        CHECK (score_type IN ('opportunity_score', 'fit_score', 'difficulty_score', 'income_potential_score', 'probability_to_win_score', 'custom')),
    CONSTRAINT opportunity_scores_score_value_chk
        CHECK (score_value BETWEEN 0 AND 100),
    CONSTRAINT opportunity_scores_score_source_chk
        CHECK (score_source IN ('ai_analysis', 'rule_engine', 'manual'))
);

CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opportunity_id uuid REFERENCES opportunities(id) ON DELETE SET NULL,
    channel text NOT NULL,
    notification_type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending',
    error_message text,
    sent_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT notifications_channel_chk
        CHECK (channel IN ('telegram', 'email', 'system', 'webhook')),
    CONSTRAINT notifications_status_chk
        CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    CONSTRAINT notifications_payload_object_chk
        CHECK (jsonb_typeof(payload) = 'object')
);

CREATE TABLE google_sheets_journal (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id uuid REFERENCES opportunities(id) ON DELETE SET NULL,
    date date NOT NULL,
    source text NOT NULL,
    opportunity_type text NOT NULL,
    title text NOT NULL,
    score numeric(5, 2),
    status text NOT NULL,
    url text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT google_sheets_journal_score_chk
        CHECK (score IS NULL OR score BETWEEN 0 AND 100)
);

CREATE TABLE source_run_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    run_status text NOT NULL,
    error_message text,
    error_details jsonb,
    execution_time_ms bigint,
    processed_count integer NOT NULL DEFAULT 0,
    saved_count integer NOT NULL DEFAULT 0,
    skipped_count integer NOT NULL DEFAULT 0,
    run_started_at timestamptz NOT NULL DEFAULT now(),
    run_finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_run_logs_run_status_chk
        CHECK (run_status IN ('running', 'succeeded', 'failed', 'partial', 'cancelled')),
    CONSTRAINT source_run_logs_error_details_object_chk
        CHECK (error_details IS NULL OR jsonb_typeof(error_details) = 'object'),
    CONSTRAINT source_run_logs_execution_time_ms_chk
        CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0),
    CONSTRAINT source_run_logs_processed_count_chk
        CHECK (processed_count >= 0),
    CONSTRAINT source_run_logs_saved_count_chk
        CHECK (saved_count >= 0),
    CONSTRAINT source_run_logs_skipped_count_chk
        CHECK (skipped_count >= 0),
    CONSTRAINT source_run_logs_finished_after_started_chk
        CHECK (run_finished_at IS NULL OR run_finished_at >= run_started_at)
);

CREATE TABLE system_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    log_source text NOT NULL,
    severity text NOT NULL,
    event_type text NOT NULL,
    message text NOT NULL,
    details jsonb,
    correlation_id text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT system_logs_severity_chk
        CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    CONSTRAINT system_logs_details_object_chk
        CHECK (details IS NULL OR jsonb_typeof(details) = 'object')
);

COMMIT;
