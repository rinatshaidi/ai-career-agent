BEGIN;

CREATE UNIQUE INDEX users_email_lower_uidx
    ON users (lower(email));

CREATE INDEX users_status_idx
    ON users (status);

CREATE INDEX sources_enabled_type_idx
    ON sources (enabled, type);

CREATE INDEX opportunities_source_id_idx
    ON opportunities (source_id);

CREATE UNIQUE INDEX opportunities_source_external_id_uidx
    ON opportunities (source_id, external_id)
    WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX opportunities_duplicate_hash_uidx
    ON opportunities (duplicate_hash);

CREATE INDEX opportunities_status_published_idx
    ON opportunities (status, published_at DESC);

CREATE INDEX opportunities_source_type_opportunity_type_idx
    ON opportunities (source_type, opportunity_type);

CREATE INDEX opportunities_collected_at_idx
    ON opportunities (collected_at DESC);

CREATE INDEX opportunity_ai_analysis_opportunity_created_idx
    ON opportunity_ai_analysis (opportunity_id, created_at DESC);

CREATE UNIQUE INDEX opportunity_ai_analysis_current_uidx
    ON opportunity_ai_analysis (opportunity_id)
    WHERE is_current;

CREATE INDEX opportunity_scores_opportunity_type_idx
    ON opportunity_scores (opportunity_id, score_type, calculated_at DESC);

CREATE UNIQUE INDEX opportunity_scores_current_uidx
    ON opportunity_scores (opportunity_id, score_type)
    WHERE is_current;

CREATE INDEX opportunity_scores_rank_idx
    ON opportunity_scores (score_type, score_value DESC)
    WHERE is_current;

CREATE INDEX notifications_user_status_created_idx
    ON notifications (user_id, status, created_at DESC);

CREATE INDEX notifications_status_channel_created_idx
    ON notifications (status, channel, created_at DESC);

CREATE INDEX notifications_opportunity_idx
    ON notifications (opportunity_id);

CREATE INDEX google_sheets_journal_date_source_idx
    ON google_sheets_journal (date DESC, source);

CREATE INDEX google_sheets_journal_opportunity_idx
    ON google_sheets_journal (opportunity_id);

CREATE INDEX source_run_logs_source_started_idx
    ON source_run_logs (source_id, run_started_at DESC);

CREATE INDEX source_run_logs_status_started_idx
    ON source_run_logs (run_status, run_started_at DESC);

CREATE INDEX system_logs_occurred_at_idx
    ON system_logs (occurred_at DESC);

CREATE INDEX system_logs_source_severity_idx
    ON system_logs (log_source, severity, occurred_at DESC);

CREATE INDEX system_logs_correlation_id_idx
    ON system_logs (correlation_id)
    WHERE correlation_id IS NOT NULL;

COMMIT;
