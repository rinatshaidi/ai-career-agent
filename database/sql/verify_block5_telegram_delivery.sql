DO $$
DECLARE
    expected_functions text[] := ARRAY[
        'delivery_upsert_telegram_target',
        'delivery_sync_telegram_outbox',
        'delivery_claim_notification_batch',
        'delivery_mark_notification_sent',
        'delivery_mark_notification_failed',
        'delivery_record_notification_action'
    ];
    current_function_name text;
BEGIN
    FOREACH current_function_name IN ARRAY expected_functions LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_proc AS procedures_catalog
            WHERE procedures_catalog.proname = current_function_name
        ) THEN
            RAISE EXCEPTION 'Missing required Block 5 function: %', current_function_name;
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'notifications'
          AND column_name = 'user_intelligence_profile_id'
    ) THEN
        RAISE EXCEPTION 'Missing column notifications.user_intelligence_profile_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'notifications'
          AND column_name = 'attempt_count'
    ) THEN
        RAISE EXCEPTION 'Missing column notifications.attempt_count';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'google_sheets_journal'
          AND column_name = 'notification_id'
    ) THEN
        RAISE EXCEPTION 'Missing column google_sheets_journal.notification_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'notifications_telegram_opportunity_match_uidx'
    ) THEN
        RAISE EXCEPTION 'Missing index notifications_telegram_opportunity_match_uidx';
    END IF;
END;
$$;

SELECT
    proname AS function_name
FROM pg_proc
WHERE proname IN (
    'delivery_upsert_telegram_target',
    'delivery_sync_telegram_outbox',
    'delivery_claim_notification_batch',
    'delivery_mark_notification_sent',
    'delivery_mark_notification_failed',
    'delivery_record_notification_action'
)
ORDER BY proname;

SELECT
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
      'notifications_telegram_opportunity_match_uidx',
      'notifications_delivery_queue_idx',
      'google_sheets_journal_notification_uidx'
  )
ORDER BY indexname;
