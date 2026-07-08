DO $$
BEGIN
    IF to_regprocedure('collection_ensure_source(text,text,boolean,text)') IS NULL THEN
        RAISE EXCEPTION 'Missing function: collection_ensure_source';
    END IF;

    IF to_regprocedure('collection_upsert_opportunity(uuid,text,text,text,text,text,text,text,text,text,text,numeric,numeric,text,timestamp with time zone,timestamp with time zone,text,text)') IS NULL THEN
        RAISE EXCEPTION 'Missing function: collection_upsert_opportunity';
    END IF;

    IF to_regprocedure('collection_ingest_source_batch(uuid,jsonb,timestamp with time zone,text)') IS NULL THEN
        RAISE EXCEPTION 'Missing function: collection_ingest_source_batch';
    END IF;
END;
$$;

SELECT
    proname AS function_name
FROM pg_proc
WHERE proname IN (
    'collection_ensure_source',
    'collection_upsert_opportunity',
    'collection_ingest_source_batch'
)
ORDER BY proname;
