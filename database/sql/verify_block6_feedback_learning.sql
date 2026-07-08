DO $$
DECLARE
    expected_tables text[] := ARRAY[
        'feedback_action_catalog',
        'user_feedback_history',
        'learning_feedback_dataset'
    ];
    expected_functions text[] := ARRAY[
        'feedback_normalize_project_type',
        'feedback_extract_matched_technologies',
        'feedback_record_notification_action',
        'feedback_mark_google_sheet_archive_synced',
        'feedback_mark_google_sheet_archive_failed',
        'feedback_purge_expired_working_memory'
    ];
    current_table_name text;
    current_function_name text;
BEGIN
    FOREACH current_table_name IN ARRAY expected_tables LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.tables AS tables_catalog
            WHERE tables_catalog.table_schema = 'public'
              AND tables_catalog.table_name = current_table_name
        ) THEN
            RAISE EXCEPTION 'Missing required Block 6 table: %', current_table_name;
        END IF;
    END LOOP;

    FOREACH current_function_name IN ARRAY expected_functions LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_proc AS procedures_catalog
            WHERE procedures_catalog.proname = current_function_name
        ) THEN
            RAISE EXCEPTION 'Missing required Block 6 function: %', current_function_name;
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS columns_catalog
        WHERE columns_catalog.table_schema = 'public'
          AND columns_catalog.table_name = 'notifications'
          AND columns_catalog.column_name = 'feedback_status'
    ) THEN
        RAISE EXCEPTION 'Missing column notifications.feedback_status';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS columns_catalog
        WHERE columns_catalog.table_schema = 'public'
          AND columns_catalog.table_name = 'google_sheets_journal'
          AND columns_catalog.column_name = 'archive_key'
    ) THEN
        RAISE EXCEPTION 'Missing column google_sheets_journal.archive_key';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS columns_catalog
        WHERE columns_catalog.table_schema = 'public'
          AND columns_catalog.table_name = 'google_sheets_journal'
          AND columns_catalog.column_name = 'sync_status'
    ) THEN
        RAISE EXCEPTION 'Missing column google_sheets_journal.sync_status';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'google_sheets_journal_archive_key_uidx'
    ) THEN
        RAISE EXCEPTION 'Missing index google_sheets_journal_archive_key_uidx';
    END IF;
END;
$$;

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'feedback_action_catalog',
      'user_feedback_history',
      'learning_feedback_dataset'
  )
ORDER BY table_name;

SELECT
    proname AS function_name
FROM pg_proc
WHERE proname IN (
    'feedback_normalize_project_type',
    'feedback_extract_matched_technologies',
    'feedback_record_notification_action',
    'feedback_mark_google_sheet_archive_synced',
    'feedback_mark_google_sheet_archive_failed',
    'feedback_purge_expired_working_memory'
)
ORDER BY proname;

SELECT
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
      'google_sheets_journal_archive_key_uidx',
      'google_sheets_journal_sync_status_idx',
      'user_feedback_history_callback_query_uidx',
      'learning_feedback_dataset_technologies_gin_idx'
  )
ORDER BY indexname;
