DO $$
DECLARE
    expected_tables text[] := ARRAY[
        'user_intelligence_profiles',
        'opportunity_analysis_jobs'
    ];
    expected_functions text[] := ARRAY[
        'decision_upsert_user_intelligence_profile',
        'decision_calculate_opportunity_score',
        'decision_determine_recommended_action',
        'decision_claim_analysis_batch',
        'decision_record_ai_analysis',
        'decision_mark_ai_analysis_failed'
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
            RAISE EXCEPTION 'Missing required Block 4 table: %', current_table_name;
        END IF;
    END LOOP;

    FOREACH current_function_name IN ARRAY expected_functions LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_proc AS procedures_catalog
            WHERE procedures_catalog.proname = current_function_name
        ) THEN
            RAISE EXCEPTION 'Missing required Block 4 function: %', current_function_name;
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS columns_catalog
        WHERE columns_catalog.table_schema = 'public'
          AND columns_catalog.table_name = 'opportunity_ai_analysis'
          AND columns_catalog.column_name = 'user_intelligence_profile_id'
    ) THEN
        RAISE EXCEPTION 'Missing column opportunity_ai_analysis.user_intelligence_profile_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS columns_catalog
        WHERE columns_catalog.table_schema = 'public'
          AND columns_catalog.table_name = 'opportunity_ai_analysis'
          AND columns_catalog.column_name = 'skills_match_score'
    ) THEN
        RAISE EXCEPTION 'Missing column opportunity_ai_analysis.skills_match_score';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS columns_catalog
        WHERE columns_catalog.table_schema = 'public'
          AND columns_catalog.table_name = 'opportunity_scores'
          AND columns_catalog.column_name = 'user_intelligence_profile_id'
    ) THEN
        RAISE EXCEPTION 'Missing column opportunity_scores.user_intelligence_profile_id';
    END IF;
END;
$$;

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'user_intelligence_profiles',
      'opportunity_analysis_jobs'
  )
ORDER BY table_name;

SELECT
    proname AS function_name
FROM pg_proc
WHERE proname IN (
    'decision_upsert_user_intelligence_profile',
    'decision_calculate_opportunity_score',
    'decision_determine_recommended_action',
    'decision_claim_analysis_batch',
    'decision_record_ai_analysis',
    'decision_mark_ai_analysis_failed'
)
ORDER BY proname;
