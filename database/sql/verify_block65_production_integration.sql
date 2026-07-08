DO $$
DECLARE
    v_upsert_definition text;
    v_sync_definition text;
    v_claim_definition text;
BEGIN
    SELECT pg_get_functiondef(pg_proc.oid)
    INTO v_upsert_definition
    FROM pg_proc
    WHERE pg_proc.proname = 'delivery_upsert_telegram_target'
    LIMIT 1;

    SELECT pg_get_functiondef(pg_proc.oid)
    INTO v_sync_definition
    FROM pg_proc
    WHERE pg_proc.proname = 'delivery_sync_telegram_outbox'
    LIMIT 1;

    SELECT pg_get_functiondef(pg_proc.oid)
    INTO v_claim_definition
    FROM pg_proc
    WHERE pg_proc.proname = 'delivery_claim_notification_batch'
    LIMIT 1;

    IF v_upsert_definition IS NULL THEN
        RAISE EXCEPTION 'delivery_upsert_telegram_target is missing';
    END IF;

    IF v_sync_definition IS NULL THEN
        RAISE EXCEPTION 'delivery_sync_telegram_outbox is missing';
    END IF;

    IF v_claim_definition IS NULL THEN
        RAISE EXCEPTION 'delivery_claim_notification_batch is missing';
    END IF;

    IF v_upsert_definition NOT LIKE '%Ri Career Agent%' THEN
        RAISE EXCEPTION 'delivery_upsert_telegram_target does not use Ri Career Agent as the default bot name';
    END IF;

    IF v_sync_definition NOT LIKE '%Ri Career Agent%' THEN
        RAISE EXCEPTION 'delivery_sync_telegram_outbox does not use Ri Career Agent as the default bot name';
    END IF;

    IF v_claim_definition NOT LIKE '%Ri Career Agent%' THEN
        RAISE EXCEPTION 'delivery_claim_notification_batch does not use Ri Career Agent as the default bot name';
    END IF;

    IF v_upsert_definition LIKE '%Ri assistant%' THEN
        RAISE EXCEPTION 'delivery_upsert_telegram_target still references Ri assistant';
    END IF;

    IF v_sync_definition LIKE '%Ri assistant%' THEN
        RAISE EXCEPTION 'delivery_sync_telegram_outbox still references Ri assistant';
    END IF;

    IF v_claim_definition LIKE '%Ri assistant%' THEN
        RAISE EXCEPTION 'delivery_claim_notification_batch still references Ri assistant';
    END IF;
END;
$$;

SELECT
    proname AS function_name
FROM pg_proc
WHERE proname IN (
    'delivery_upsert_telegram_target',
    'delivery_sync_telegram_outbox',
    'delivery_claim_notification_batch'
)
ORDER BY proname;
