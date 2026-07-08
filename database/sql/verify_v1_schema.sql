DO $$
DECLARE
    expected_tables text[] := ARRAY[
        'users',
        'user_profiles',
        'sources',
        'opportunities',
        'opportunity_ai_analysis',
        'opportunity_scores',
        'notifications',
        'google_sheets_journal',
        'source_run_logs',
        'system_logs'
    ];
    expected_indexes text[] := ARRAY[
        'users_email_lower_uidx',
        'opportunities_source_external_id_uidx',
        'opportunities_duplicate_hash_uidx',
        'opportunity_ai_analysis_current_uidx',
        'opportunity_scores_current_uidx',
        'notifications_status_channel_created_idx',
        'source_run_logs_source_started_idx',
        'system_logs_source_severity_idx',
        'system_logs_correlation_id_idx'
    ];
    current_table_name text;
    current_index_name text;
BEGIN
    FOREACH current_table_name IN ARRAY expected_tables LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.tables AS tables_catalog
            WHERE tables_catalog.table_schema = 'public'
              AND tables_catalog.table_name = current_table_name
        ) THEN
            RAISE EXCEPTION 'Missing required table: %', current_table_name;
        END IF;
    END LOOP;

    FOREACH current_index_name IN ARRAY expected_indexes LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes AS indexes_catalog
            WHERE indexes_catalog.schemaname = 'public'
              AND indexes_catalog.indexname = current_index_name
        ) THEN
            RAISE EXCEPTION 'Missing required index: %', current_index_name;
        END IF;
    END LOOP;
END;
$$;

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'users',
      'user_profiles',
      'sources',
      'opportunities',
      'opportunity_ai_analysis',
      'opportunity_scores',
      'notifications',
      'google_sheets_journal',
      'source_run_logs',
      'system_logs'
  )
ORDER BY table_name;

SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
      'users',
      'sources',
      'opportunities',
      'opportunity_ai_analysis',
      'opportunity_scores',
      'notifications',
      'google_sheets_journal',
      'source_run_logs',
      'system_logs'
  )
ORDER BY tablename, indexname;
