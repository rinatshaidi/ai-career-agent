BEGIN;

CREATE OR REPLACE FUNCTION collection_ensure_source(
    p_name text,
    p_type text,
    p_enabled boolean DEFAULT true,
    p_config_reference text DEFAULT NULL
)
RETURNS TABLE (
    source_id uuid,
    source_name text,
    source_catalog_type text,
    config_reference text
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH upserted AS (
        INSERT INTO sources (
            name,
            type,
            enabled,
            config_reference
        )
        VALUES (
            p_name,
            p_type,
            p_enabled,
            p_config_reference
        )
        ON CONFLICT (name, type)
        DO UPDATE SET
            enabled = EXCLUDED.enabled,
            config_reference = EXCLUDED.config_reference,
            updated_at = now()
        RETURNING id, name, type, config_reference
    )
    SELECT
        upserted.id,
        upserted.name,
        upserted.type,
        upserted.config_reference
    FROM upserted;
END;
$$;

CREATE OR REPLACE FUNCTION collection_upsert_opportunity(
    p_source_id uuid,
    p_external_id text,
    p_title text,
    p_description text,
    p_raw_text text,
    p_url text,
    p_company_name text,
    p_opportunity_type text,
    p_source_type text,
    p_location text,
    p_remote_type text,
    p_budget_min numeric,
    p_budget_max numeric,
    p_currency text,
    p_published_at timestamptz,
    p_collected_at timestamptz,
    p_status text,
    p_dedupe_key text
)
RETURNS TABLE (
    opportunity_id uuid,
    action text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_existing opportunities%ROWTYPE;
    v_duplicate_hash char(64);
    v_effective_status text := COALESCE(NULLIF(trim(p_status), ''), 'new');
    v_effective_collected_at timestamptz := COALESCE(p_collected_at, now());
    v_effective_remote_type text := COALESCE(NULLIF(trim(p_remote_type), ''), 'unknown');
    v_effective_source_type text := COALESCE(NULLIF(trim(p_source_type), ''), 'other');
    v_effective_opportunity_type text := COALESCE(NULLIF(trim(p_opportunity_type), ''), 'other');
    v_effective_currency char(3);
    v_effective_dedupe_key text;
BEGIN
    v_effective_dedupe_key := lower(trim(COALESCE(
        NULLIF(p_dedupe_key, ''),
        concat_ws(
            ' | ',
            p_title,
            p_company_name,
            p_url,
            p_location,
            to_char(p_published_at, 'YYYY-MM-DD"T"HH24:MI:SSOF')
        )
    )));

    v_duplicate_hash := encode(digest(v_effective_dedupe_key, 'sha256'), 'hex')::char(64);
    v_effective_currency := CASE
        WHEN p_currency IS NULL OR trim(p_currency) = '' THEN NULL
        ELSE upper(trim(p_currency))::char(3)
    END;

    IF p_external_id IS NOT NULL THEN
        SELECT *
        INTO v_existing
        FROM opportunities
        WHERE source_id = p_source_id
          AND external_id = p_external_id
        LIMIT 1;
    END IF;

    IF NOT FOUND THEN
        SELECT *
        INTO v_existing
        FROM opportunities
        WHERE duplicate_hash = v_duplicate_hash
        LIMIT 1;
    END IF;

    IF NOT FOUND THEN
        INSERT INTO opportunities (
            source_id,
            external_id,
            title,
            description,
            raw_text,
            url,
            company_name,
            opportunity_type,
            source_type,
            location,
            remote_type,
            budget_min,
            budget_max,
            currency,
            published_at,
            collected_at,
            status,
            duplicate_hash
        )
        VALUES (
            p_source_id,
            p_external_id,
            p_title,
            p_description,
            p_raw_text,
            p_url,
            p_company_name,
            v_effective_opportunity_type,
            v_effective_source_type,
            p_location,
            v_effective_remote_type,
            p_budget_min,
            p_budget_max,
            v_effective_currency,
            p_published_at,
            v_effective_collected_at,
            v_effective_status,
            v_duplicate_hash
        )
        RETURNING id
        INTO opportunity_id;

        action := 'inserted';
        RETURN NEXT;
        RETURN;
    END IF;

    opportunity_id := v_existing.id;

    IF v_existing.title IS DISTINCT FROM p_title
        OR v_existing.description IS DISTINCT FROM p_description
        OR v_existing.raw_text IS DISTINCT FROM p_raw_text
        OR v_existing.url IS DISTINCT FROM p_url
        OR v_existing.company_name IS DISTINCT FROM p_company_name
        OR v_existing.opportunity_type IS DISTINCT FROM v_effective_opportunity_type
        OR v_existing.source_type IS DISTINCT FROM v_effective_source_type
        OR v_existing.location IS DISTINCT FROM p_location
        OR v_existing.remote_type IS DISTINCT FROM v_effective_remote_type
        OR v_existing.budget_min IS DISTINCT FROM p_budget_min
        OR v_existing.budget_max IS DISTINCT FROM p_budget_max
        OR v_existing.currency IS DISTINCT FROM v_effective_currency
        OR v_existing.published_at IS DISTINCT FROM p_published_at
        OR v_existing.status IS DISTINCT FROM v_effective_status
    THEN
        UPDATE opportunities
        SET
            external_id = COALESCE(opportunities.external_id, p_external_id),
            title = p_title,
            description = p_description,
            raw_text = p_raw_text,
            url = p_url,
            company_name = p_company_name,
            opportunity_type = v_effective_opportunity_type,
            source_type = v_effective_source_type,
            location = p_location,
            remote_type = v_effective_remote_type,
            budget_min = p_budget_min,
            budget_max = p_budget_max,
            currency = v_effective_currency,
            published_at = p_published_at,
            collected_at = v_effective_collected_at,
            status = v_effective_status,
            duplicate_hash = v_duplicate_hash,
            updated_at = now()
        WHERE id = v_existing.id;

        action := 'updated';
    ELSE
        action := 'skipped';
    END IF;

    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION collection_ingest_source_batch(
    p_source_id uuid,
    p_items jsonb,
    p_run_started_at timestamptz,
    p_fetch_error text DEFAULT NULL
)
RETURNS TABLE (
    source_id uuid,
    run_status text,
    processed_count integer,
    saved_count integer,
    skipped_count integer,
    error_message text,
    run_finished_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_item jsonb;
    v_action text;
    v_opportunity_id uuid;
    v_processed_count integer := 0;
    v_saved_count integer := 0;
    v_skipped_count integer := 0;
    v_error_messages text[] := ARRAY[]::text[];
    v_run_status text;
    v_run_finished_at timestamptz := now();
    v_error_message text;
BEGIN
    IF p_fetch_error IS NULL OR trim(p_fetch_error) = '' THEN
        FOR v_item IN
            SELECT value
            FROM jsonb_array_elements(COALESCE(p_items, '[]'::jsonb))
        LOOP
            v_processed_count := v_processed_count + 1;

            BEGIN
                SELECT
                    result.opportunity_id,
                    result.action
                INTO
                    v_opportunity_id,
                    v_action
                FROM collection_upsert_opportunity(
                    p_source_id,
                    NULLIF(v_item->>'external_id', ''),
                    v_item->>'title',
                    NULLIF(v_item->>'description', ''),
                    NULLIF(v_item->>'raw_text', ''),
                    NULLIF(v_item->>'url', ''),
                    NULLIF(v_item->>'company_name', ''),
                    NULLIF(v_item->>'opportunity_type', ''),
                    NULLIF(v_item->>'source_type', ''),
                    NULLIF(v_item->>'location', ''),
                    NULLIF(v_item->>'remote_type', ''),
                    NULLIF(v_item->>'budget_min', '')::numeric,
                    NULLIF(v_item->>'budget_max', '')::numeric,
                    NULLIF(v_item->>'currency', ''),
                    NULLIF(v_item->>'published_at', '')::timestamptz,
                    NULLIF(v_item->>'collected_at', '')::timestamptz,
                    NULLIF(v_item->>'status', ''),
                    NULLIF(v_item->>'dedupe_key', '')
                ) AS result;

                IF v_action IN ('inserted', 'updated') THEN
                    v_saved_count := v_saved_count + 1;
                ELSE
                    v_skipped_count := v_skipped_count + 1;
                END IF;
            EXCEPTION
                WHEN OTHERS THEN
                    v_skipped_count := v_skipped_count + 1;
                    v_error_messages := array_append(
                        v_error_messages,
                        format(
                            '%s: %s',
                            COALESCE(NULLIF(v_item->>'external_id', ''), left(COALESCE(v_item->>'title', 'unknown'), 120)),
                            SQLERRM
                        )
                    );
            END;
        END LOOP;
    ELSE
        v_error_messages := array_append(v_error_messages, p_fetch_error);
    END IF;

    IF array_length(v_error_messages, 1) IS NULL THEN
        v_run_status := 'succeeded';
    ELSIF v_saved_count > 0 OR v_processed_count > 0 THEN
        v_run_status := 'partial';
    ELSE
        v_run_status := 'failed';
    END IF;

    v_error_message := CASE
        WHEN array_length(v_error_messages, 1) IS NULL THEN NULL
        ELSE array_to_string(v_error_messages, ' | ')
    END;

    INSERT INTO source_run_logs (
        source_id,
        run_status,
        error_message,
        error_details,
        execution_time_ms,
        processed_count,
        saved_count,
        skipped_count,
        run_started_at,
        run_finished_at
    )
    VALUES (
        p_source_id,
        v_run_status,
        v_error_message,
        CASE
            WHEN array_length(v_error_messages, 1) IS NULL THEN NULL
            ELSE jsonb_build_object('errors', to_jsonb(v_error_messages))
        END,
        GREATEST(0, floor(extract(epoch FROM (v_run_finished_at - COALESCE(p_run_started_at, v_run_finished_at))) * 1000))::bigint,
        v_processed_count,
        v_saved_count,
        v_skipped_count,
        COALESCE(p_run_started_at, v_run_finished_at),
        v_run_finished_at
    );

    UPDATE sources
    SET
        last_success_at = CASE
            WHEN v_run_status IN ('succeeded', 'partial') THEN v_run_finished_at
            ELSE last_success_at
        END,
        last_error_at = CASE
            WHEN v_run_status IN ('failed', 'partial') THEN v_run_finished_at
            ELSE last_error_at
        END,
        updated_at = now()
    WHERE id = p_source_id;

    IF array_length(v_error_messages, 1) IS NOT NULL THEN
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
            'collect-opportunities',
            CASE
                WHEN v_run_status = 'failed' THEN 'error'
                ELSE 'warning'
            END,
            'source_collection_issue',
            format('Collection issue for source %s', p_source_id),
            jsonb_build_object(
                'source_id', p_source_id,
                'run_status', v_run_status,
                'errors', to_jsonb(v_error_messages)
            ),
            p_source_id::text,
            v_run_finished_at
        );
    END IF;

    RETURN QUERY
    SELECT
        p_source_id,
        v_run_status,
        v_processed_count,
        v_saved_count,
        v_skipped_count,
        v_error_message,
        v_run_finished_at;
END;
$$;

COMMIT;
