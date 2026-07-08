BEGIN;

CREATE TABLE user_intelligence_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_slug text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    core_skills text[] NOT NULL DEFAULT ARRAY[]::text[],
    technology_stack text[] NOT NULL DEFAULT ARRAY[]::text[],
    preferred_project_types text[] NOT NULL DEFAULT ARRAY[]::text[],
    undesirable_project_types text[] NOT NULL DEFAULT ARRAY[]::text[],
    minimum_project_budget numeric(14, 2),
    preferred_currency char(3),
    english_level text NOT NULL DEFAULT 'unknown',
    experience_level text NOT NULL DEFAULT 'unknown',
    include_keywords text[] NOT NULL DEFAULT ARRAY[]::text[],
    exclude_keywords text[] NOT NULL DEFAULT ARRAY[]::text[],
    priority_directions text[] NOT NULL DEFAULT ARRAY[]::text[],
    additional_preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
    scoring_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_intelligence_profiles_user_id_key UNIQUE (user_id),
    CONSTRAINT user_intelligence_profiles_profile_slug_key UNIQUE (profile_slug),
    CONSTRAINT user_intelligence_profiles_status_chk
        CHECK (status IN ('draft', 'active', 'archived')),
    CONSTRAINT user_intelligence_profiles_budget_chk
        CHECK (minimum_project_budget IS NULL OR minimum_project_budget >= 0),
    CONSTRAINT user_intelligence_profiles_currency_chk
        CHECK (preferred_currency IS NULL OR preferred_currency::text ~ '^[A-Z]{3}$'),
    CONSTRAINT user_intelligence_profiles_english_level_chk
        CHECK (english_level IN ('unknown', 'a1', 'a2', 'b1', 'b2', 'c1', 'c2', 'native')),
    CONSTRAINT user_intelligence_profiles_experience_level_chk
        CHECK (experience_level IN ('unknown', 'junior', 'middle', 'senior', 'lead', 'principal', 'architect', 'expert')),
    CONSTRAINT user_intelligence_profiles_additional_preferences_object_chk
        CHECK (jsonb_typeof(additional_preferences) = 'object'),
    CONSTRAINT user_intelligence_profiles_scoring_policy_object_chk
        CHECK (jsonb_typeof(scoring_policy) = 'object')
);

CREATE TABLE opportunity_analysis_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id uuid NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    user_intelligence_profile_id uuid NOT NULL REFERENCES user_intelligence_profiles(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0,
    last_error_message text,
    last_error_details jsonb,
    locked_at timestamptz,
    locked_by text,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT opportunity_analysis_jobs_opportunity_profile_key UNIQUE (opportunity_id, user_intelligence_profile_id),
    CONSTRAINT opportunity_analysis_jobs_status_chk
        CHECK (status IN ('pending', 'in_progress', 'succeeded', 'retry', 'failed', 'cancelled')),
    CONSTRAINT opportunity_analysis_jobs_attempt_count_chk
        CHECK (attempt_count >= 0),
    CONSTRAINT opportunity_analysis_jobs_error_details_object_chk
        CHECK (last_error_details IS NULL OR jsonb_typeof(last_error_details) = 'object'),
    CONSTRAINT opportunity_analysis_jobs_completed_after_created_chk
        CHECK (completed_at IS NULL OR completed_at >= created_at)
);

ALTER TABLE opportunity_ai_analysis
    ADD COLUMN user_intelligence_profile_id uuid NOT NULL REFERENCES user_intelligence_profiles(id) ON DELETE CASCADE,
    ADD COLUMN llm_provider text NOT NULL DEFAULT 'openai',
    ADD COLUMN prompt_version text NOT NULL DEFAULT 'block4-v1',
    ADD COLUMN llm_response_id text,
    ADD COLUMN is_recommended boolean NOT NULL DEFAULT false,
    ADD COLUMN why_fit jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN why_not_fit jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN urgency_score numeric(5, 2),
    ADD COLUMN skills_match_score numeric(5, 2),
    ADD COLUMN decision_confidence_score numeric(5, 2),
    ADD COLUMN input_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN analysis_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN analyzed_at timestamptz NOT NULL DEFAULT now(),
    ADD CONSTRAINT opportunity_ai_analysis_llm_provider_chk
        CHECK (llm_provider IN ('openai', 'azure_openai', 'anthropic', 'google', 'open_source', 'other')),
    ADD CONSTRAINT opportunity_ai_analysis_why_fit_array_chk
        CHECK (jsonb_typeof(why_fit) = 'array'),
    ADD CONSTRAINT opportunity_ai_analysis_why_not_fit_array_chk
        CHECK (jsonb_typeof(why_not_fit) = 'array'),
    ADD CONSTRAINT opportunity_ai_analysis_urgency_score_chk
        CHECK (urgency_score IS NULL OR urgency_score BETWEEN 0 AND 100),
    ADD CONSTRAINT opportunity_ai_analysis_skills_match_score_chk
        CHECK (skills_match_score IS NULL OR skills_match_score BETWEEN 0 AND 100),
    ADD CONSTRAINT opportunity_ai_analysis_decision_confidence_score_chk
        CHECK (decision_confidence_score IS NULL OR decision_confidence_score BETWEEN 0 AND 100),
    ADD CONSTRAINT opportunity_ai_analysis_input_snapshot_object_chk
        CHECK (jsonb_typeof(input_snapshot) = 'object'),
    ADD CONSTRAINT opportunity_ai_analysis_analysis_payload_object_chk
        CHECK (jsonb_typeof(analysis_payload) = 'object');

ALTER TABLE opportunity_scores
    ADD COLUMN user_intelligence_profile_id uuid NOT NULL REFERENCES user_intelligence_profiles(id) ON DELETE CASCADE;

ALTER TABLE opportunity_scores
    DROP CONSTRAINT opportunity_scores_score_type_chk;

ALTER TABLE opportunity_scores
    ADD CONSTRAINT opportunity_scores_score_type_chk
        CHECK (
            score_type IN (
                'opportunity_score',
                'fit_score',
                'difficulty_score',
                'income_potential_score',
                'probability_to_win_score',
                'urgency_score',
                'skills_match_score',
                'custom'
            )
        );

DROP INDEX opportunity_ai_analysis_opportunity_created_idx;
CREATE INDEX opportunity_ai_analysis_opportunity_created_idx
    ON opportunity_ai_analysis (opportunity_id, user_intelligence_profile_id, created_at DESC);

DROP INDEX opportunity_ai_analysis_current_uidx;
CREATE UNIQUE INDEX opportunity_ai_analysis_current_uidx
    ON opportunity_ai_analysis (opportunity_id, user_intelligence_profile_id)
    WHERE is_current;

DROP INDEX opportunity_scores_opportunity_type_idx;
CREATE INDEX opportunity_scores_opportunity_type_idx
    ON opportunity_scores (opportunity_id, user_intelligence_profile_id, score_type, calculated_at DESC);

DROP INDEX opportunity_scores_current_uidx;
CREATE UNIQUE INDEX opportunity_scores_current_uidx
    ON opportunity_scores (opportunity_id, user_intelligence_profile_id, score_type)
    WHERE is_current;

DROP INDEX opportunity_scores_rank_idx;
CREATE INDEX opportunity_scores_rank_idx
    ON opportunity_scores (user_intelligence_profile_id, score_type, score_value DESC)
    WHERE is_current;

CREATE INDEX user_intelligence_profiles_status_idx
    ON user_intelligence_profiles (status);

CREATE INDEX opportunity_analysis_jobs_status_next_attempt_idx
    ON opportunity_analysis_jobs (user_intelligence_profile_id, status, next_attempt_at, created_at);

CREATE INDEX opportunity_analysis_jobs_opportunity_status_idx
    ON opportunity_analysis_jobs (opportunity_id, status, created_at DESC);

CREATE INDEX opportunity_ai_analysis_profile_action_idx
    ON opportunity_ai_analysis (user_intelligence_profile_id, recommended_action, analyzed_at DESC)
    WHERE is_current;

CREATE TRIGGER user_intelligence_profiles_set_updated_at
    BEFORE UPDATE ON user_intelligence_profiles
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

CREATE TRIGGER opportunity_analysis_jobs_set_updated_at
    BEFORE UPDATE ON opportunity_analysis_jobs
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE FUNCTION decision_upsert_user_intelligence_profile(
    p_user_id uuid,
    p_profile_slug text,
    p_status text DEFAULT 'active',
    p_core_skills text[] DEFAULT NULL,
    p_technology_stack text[] DEFAULT NULL,
    p_preferred_project_types text[] DEFAULT NULL,
    p_undesirable_project_types text[] DEFAULT NULL,
    p_minimum_project_budget numeric DEFAULT NULL,
    p_preferred_currency text DEFAULT NULL,
    p_english_level text DEFAULT 'unknown',
    p_experience_level text DEFAULT 'unknown',
    p_include_keywords text[] DEFAULT NULL,
    p_exclude_keywords text[] DEFAULT NULL,
    p_priority_directions text[] DEFAULT NULL,
    p_additional_preferences jsonb DEFAULT '{}'::jsonb,
    p_scoring_policy jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    profile_id uuid,
    profile_slug text,
    profile_status text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_slug text;
    v_preferred_currency char(3);
BEGIN
    v_profile_slug := lower(regexp_replace(COALESCE(NULLIF(trim(p_profile_slug), ''), p_user_id::text), '[^a-z0-9]+', '-', 'g'));
    v_profile_slug := trim(both '-' FROM v_profile_slug);
    v_preferred_currency := CASE
        WHEN p_preferred_currency IS NULL OR trim(p_preferred_currency) = '' THEN NULL
        ELSE upper(trim(p_preferred_currency))::char(3)
    END;

    RETURN QUERY
    WITH upserted AS (
        INSERT INTO user_intelligence_profiles (
            user_id,
            profile_slug,
            status,
            core_skills,
            technology_stack,
            preferred_project_types,
            undesirable_project_types,
            minimum_project_budget,
            preferred_currency,
            english_level,
            experience_level,
            include_keywords,
            exclude_keywords,
            priority_directions,
            additional_preferences,
            scoring_policy
        )
        VALUES (
            p_user_id,
            v_profile_slug,
            COALESCE(NULLIF(trim(p_status), ''), 'active'),
            COALESCE(p_core_skills, ARRAY[]::text[]),
            COALESCE(p_technology_stack, ARRAY[]::text[]),
            COALESCE(p_preferred_project_types, ARRAY[]::text[]),
            COALESCE(p_undesirable_project_types, ARRAY[]::text[]),
            p_minimum_project_budget,
            v_preferred_currency,
            COALESCE(NULLIF(lower(trim(p_english_level)), ''), 'unknown'),
            COALESCE(NULLIF(lower(trim(p_experience_level)), ''), 'unknown'),
            COALESCE(p_include_keywords, ARRAY[]::text[]),
            COALESCE(p_exclude_keywords, ARRAY[]::text[]),
            COALESCE(p_priority_directions, ARRAY[]::text[]),
            COALESCE(p_additional_preferences, '{}'::jsonb),
            COALESCE(p_scoring_policy, '{}'::jsonb)
        )
        ON CONFLICT (user_id)
        DO UPDATE SET
            profile_slug = EXCLUDED.profile_slug,
            status = EXCLUDED.status,
            core_skills = EXCLUDED.core_skills,
            technology_stack = EXCLUDED.technology_stack,
            preferred_project_types = EXCLUDED.preferred_project_types,
            undesirable_project_types = EXCLUDED.undesirable_project_types,
            minimum_project_budget = EXCLUDED.minimum_project_budget,
            preferred_currency = EXCLUDED.preferred_currency,
            english_level = EXCLUDED.english_level,
            experience_level = EXCLUDED.experience_level,
            include_keywords = EXCLUDED.include_keywords,
            exclude_keywords = EXCLUDED.exclude_keywords,
            priority_directions = EXCLUDED.priority_directions,
            additional_preferences = EXCLUDED.additional_preferences,
            scoring_policy = EXCLUDED.scoring_policy,
            updated_at = now()
        RETURNING id, profile_slug, status
    )
    SELECT
        upserted.id,
        upserted.profile_slug,
        upserted.status
    FROM upserted;
END;
$$;

CREATE OR REPLACE FUNCTION decision_calculate_opportunity_score(
    p_fit_score numeric,
    p_probability_to_win_score numeric,
    p_income_potential_score numeric,
    p_urgency_score numeric,
    p_skills_match_score numeric,
    p_difficulty_score numeric,
    p_scoring_policy jsonb DEFAULT '{}'::jsonb
)
RETURNS numeric
LANGUAGE plpgsql
AS $$
DECLARE
    v_weights jsonb := COALESCE(p_scoring_policy -> 'scoring_weights', '{}'::jsonb);
    v_fit_weight numeric := COALESCE(NULLIF(v_weights ->> 'fit_score', '')::numeric, 30);
    v_skills_weight numeric := COALESCE(NULLIF(v_weights ->> 'skills_match_score', '')::numeric, 20);
    v_probability_weight numeric := COALESCE(NULLIF(v_weights ->> 'probability_to_win_score', '')::numeric, 20);
    v_income_weight numeric := COALESCE(NULLIF(v_weights ->> 'income_potential_score', '')::numeric, 15);
    v_urgency_weight numeric := COALESCE(NULLIF(v_weights ->> 'urgency_score', '')::numeric, 10);
    v_difficulty_inverse_weight numeric := COALESCE(NULLIF(v_weights ->> 'difficulty_inverse_score', '')::numeric, 5);
    v_total_weight numeric;
    v_raw_score numeric;
BEGIN
    v_total_weight := GREATEST(
        1,
        v_fit_weight
        + v_skills_weight
        + v_probability_weight
        + v_income_weight
        + v_urgency_weight
        + v_difficulty_inverse_weight
    );

    v_raw_score := (
        COALESCE(p_fit_score, 0) * v_fit_weight
        + COALESCE(p_skills_match_score, 0) * v_skills_weight
        + COALESCE(p_probability_to_win_score, 0) * v_probability_weight
        + COALESCE(p_income_potential_score, 0) * v_income_weight
        + COALESCE(p_urgency_score, 0) * v_urgency_weight
        + GREATEST(0, 100 - COALESCE(p_difficulty_score, 100)) * v_difficulty_inverse_weight
    ) / v_total_weight;

    RETURN LEAST(100, GREATEST(0, round(v_raw_score, 2)));
END;
$$;

CREATE OR REPLACE FUNCTION decision_determine_recommended_action(
    p_is_recommended boolean,
    p_opportunity_score numeric,
    p_scoring_policy jsonb DEFAULT '{}'::jsonb
)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    v_thresholds jsonb := COALESCE(p_scoring_policy -> 'thresholds', '{}'::jsonb);
    v_apply_now_threshold numeric := COALESCE(NULLIF(v_thresholds ->> 'apply_now', '')::numeric, 80);
    v_review_threshold numeric := COALESCE(NULLIF(v_thresholds ->> 'review_manually', '')::numeric, 65);
    v_watchlist_threshold numeric := COALESCE(NULLIF(v_thresholds ->> 'watchlist', '')::numeric, 50);
BEGIN
    IF COALESCE(p_is_recommended, false) = false THEN
        RETURN 'skip';
    END IF;

    IF COALESCE(p_opportunity_score, 0) >= v_apply_now_threshold THEN
        RETURN 'apply_now';
    END IF;

    IF COALESCE(p_opportunity_score, 0) >= v_review_threshold THEN
        RETURN 'review_manually';
    END IF;

    IF COALESCE(p_opportunity_score, 0) >= v_watchlist_threshold THEN
        RETURN 'watchlist';
    END IF;

    RETURN 'skip';
END;
$$;

CREATE OR REPLACE FUNCTION decision_claim_analysis_batch(
    p_profile_slug text DEFAULT NULL,
    p_batch_size integer DEFAULT 10,
    p_lock_token text DEFAULT NULL
)
RETURNS TABLE (
    job_id uuid,
    opportunity_id uuid,
    user_intelligence_profile_id uuid,
    profile_slug text,
    lock_token text,
    opportunity_payload jsonb,
    profile_payload jsonb,
    scoring_policy jsonb
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile user_intelligence_profiles%ROWTYPE;
    v_lock_token text := COALESCE(NULLIF(trim(p_lock_token), ''), gen_random_uuid()::text);
    v_batch_size integer := GREATEST(COALESCE(p_batch_size, 10), 1);
BEGIN
    SELECT *
    INTO v_profile
    FROM user_intelligence_profiles
    WHERE status = 'active'
      AND (p_profile_slug IS NULL OR profile_slug = p_profile_slug)
    ORDER BY updated_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No active user intelligence profile found for slug: %', COALESCE(p_profile_slug, '<default>');
    END IF;

    INSERT INTO opportunity_analysis_jobs (
        opportunity_id,
        user_intelligence_profile_id,
        status
    )
    SELECT
        opportunities.id,
        v_profile.id,
        'pending'
    FROM opportunities
    WHERE opportunities.status IN ('new', 'review_pending')
      AND NOT EXISTS (
          SELECT 1
          FROM opportunity_analysis_jobs AS jobs
          WHERE jobs.opportunity_id = opportunities.id
            AND jobs.user_intelligence_profile_id = v_profile.id
      )
    ORDER BY COALESCE(opportunities.published_at, opportunities.collected_at) DESC NULLS LAST, opportunities.created_at DESC
    LIMIT v_batch_size * 5
    ON CONFLICT (opportunity_id, user_intelligence_profile_id) DO NOTHING;

    UPDATE opportunity_analysis_jobs AS jobs
    SET
        status = 'pending',
        next_attempt_at = now(),
        completed_at = NULL,
        locked_at = NULL,
        locked_by = NULL,
        updated_at = now()
    FROM opportunities
    WHERE jobs.user_intelligence_profile_id = v_profile.id
      AND jobs.status = 'succeeded'
      AND opportunities.id = jobs.opportunity_id
      AND NOT EXISTS (
          SELECT 1
          FROM opportunity_ai_analysis AS current_analysis
          WHERE current_analysis.opportunity_id = jobs.opportunity_id
            AND current_analysis.user_intelligence_profile_id = jobs.user_intelligence_profile_id
            AND current_analysis.is_current
            AND opportunities.updated_at <= current_analysis.analyzed_at
            AND v_profile.updated_at <= current_analysis.analyzed_at
      );

    RETURN QUERY
    WITH claimable AS (
        SELECT jobs.id
        FROM opportunity_analysis_jobs AS jobs
        JOIN opportunities
            ON opportunities.id = jobs.opportunity_id
        WHERE jobs.user_intelligence_profile_id = v_profile.id
          AND jobs.status IN ('pending', 'retry')
          AND jobs.next_attempt_at <= now()
        ORDER BY COALESCE(opportunities.published_at, opportunities.collected_at) DESC NULLS LAST, jobs.created_at
        LIMIT v_batch_size
        FOR UPDATE SKIP LOCKED
    ),
    claimed AS (
        UPDATE opportunity_analysis_jobs AS jobs
        SET
            status = 'in_progress',
            attempt_count = jobs.attempt_count + 1,
            locked_at = now(),
            locked_by = v_lock_token,
            updated_at = now()
        FROM claimable
        WHERE jobs.id = claimable.id
        RETURNING jobs.*
    )
    SELECT
        claimed.id,
        claimed.opportunity_id,
        claimed.user_intelligence_profile_id,
        v_profile.profile_slug,
        v_lock_token,
        jsonb_build_object(
            'id', opportunities.id,
            'source_id', opportunities.source_id,
            'title', opportunities.title,
            'description', opportunities.description,
            'raw_text', opportunities.raw_text,
            'url', opportunities.url,
            'company_name', opportunities.company_name,
            'opportunity_type', opportunities.opportunity_type,
            'source_type', opportunities.source_type,
            'location', opportunities.location,
            'remote_type', opportunities.remote_type,
            'budget_min', opportunities.budget_min,
            'budget_max', opportunities.budget_max,
            'currency', opportunities.currency,
            'published_at', opportunities.published_at,
            'collected_at', opportunities.collected_at,
            'status', opportunities.status
        ),
        jsonb_build_object(
            'id', v_profile.id,
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
            'additional_preferences', v_profile.additional_preferences,
            'scoring_policy', v_profile.scoring_policy
        ),
        v_profile.scoring_policy
    FROM claimed
    JOIN opportunities
        ON opportunities.id = claimed.opportunity_id
    ORDER BY COALESCE(opportunities.published_at, opportunities.collected_at) DESC NULLS LAST, claimed.created_at;
END;
$$;

CREATE OR REPLACE FUNCTION decision_record_ai_analysis(
    p_job_id uuid,
    p_analysis jsonb,
    p_model_name text,
    p_llm_provider text DEFAULT 'openai',
    p_prompt_version text DEFAULT 'block4-v1',
    p_llm_response_id text DEFAULT NULL,
    p_input_snapshot jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    analysis_id uuid,
    opportunity_id uuid,
    user_intelligence_profile_id uuid,
    opportunity_score numeric,
    recommended_action text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_job opportunity_analysis_jobs%ROWTYPE;
    v_profile user_intelligence_profiles%ROWTYPE;
    v_analysis_id uuid;
    v_fit_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'fit_score', '')), '')::numeric;
    v_probability_to_win_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'probability_to_win_score', '')), '')::numeric;
    v_difficulty_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'difficulty_score', '')), '')::numeric;
    v_income_potential_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'income_potential_score', '')), '')::numeric;
    v_urgency_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'urgency_score', '')), '')::numeric;
    v_skills_match_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'skills_match_score', '')), '')::numeric;
    v_decision_confidence_score numeric := NULLIF(trim(COALESCE(p_analysis ->> 'decision_confidence_score', '')), '')::numeric;
    v_is_recommended boolean := COALESCE((p_analysis ->> 'is_recommended')::boolean, false);
    v_opportunity_score numeric;
    v_recommended_action text;
    v_summary text := COALESCE(NULLIF(trim(p_analysis ->> 'summary'), ''), 'AI decision completed without summary.');
    v_why_fit jsonb := COALESCE(p_analysis -> 'why_fit', '[]'::jsonb);
    v_why_not_fit jsonb := COALESCE(p_analysis -> 'why_not_fit', '[]'::jsonb);
    v_risks jsonb := COALESCE(p_analysis -> 'risks', '[]'::jsonb);
BEGIN
    IF p_analysis IS NULL OR jsonb_typeof(p_analysis) <> 'object' THEN
        RAISE EXCEPTION 'decision_record_ai_analysis expects an object JSON payload';
    END IF;

    SELECT *
    INTO v_job
    FROM opportunity_analysis_jobs
    WHERE id = p_job_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Analysis job not found: %', p_job_id;
    END IF;

    SELECT *
    INTO v_profile
    FROM user_intelligence_profiles
    WHERE id = v_job.user_intelligence_profile_id;

    v_opportunity_score := decision_calculate_opportunity_score(
        v_fit_score,
        v_probability_to_win_score,
        v_income_potential_score,
        v_urgency_score,
        v_skills_match_score,
        v_difficulty_score,
        v_profile.scoring_policy
    );

    v_recommended_action := decision_determine_recommended_action(
        v_is_recommended,
        v_opportunity_score,
        v_profile.scoring_policy
    );

    UPDATE opportunity_ai_analysis
    SET is_current = false
    WHERE opportunity_id = v_job.opportunity_id
      AND user_intelligence_profile_id = v_job.user_intelligence_profile_id
      AND is_current;

    INSERT INTO opportunity_ai_analysis (
        opportunity_id,
        user_intelligence_profile_id,
        summary,
        fit_score,
        opportunity_score,
        difficulty_score,
        income_potential_score,
        probability_to_win_score,
        urgency_score,
        skills_match_score,
        decision_confidence_score,
        reasons_to_apply,
        risks,
        recommended_action,
        model_name,
        llm_provider,
        prompt_version,
        llm_response_id,
        is_recommended,
        why_fit,
        why_not_fit,
        input_snapshot,
        analysis_payload,
        analyzed_at,
        is_current
    )
    VALUES (
        v_job.opportunity_id,
        v_job.user_intelligence_profile_id,
        v_summary,
        v_fit_score,
        v_opportunity_score,
        v_difficulty_score,
        v_income_potential_score,
        v_probability_to_win_score,
        v_urgency_score,
        v_skills_match_score,
        v_decision_confidence_score,
        v_why_fit,
        v_risks,
        v_recommended_action,
        p_model_name,
        COALESCE(NULLIF(trim(p_llm_provider), ''), 'openai'),
        COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'),
        NULLIF(trim(p_llm_response_id), ''),
        v_is_recommended,
        v_why_fit,
        v_why_not_fit,
        COALESCE(p_input_snapshot, '{}'::jsonb),
        p_analysis,
        now(),
        true
    )
    RETURNING id
    INTO v_analysis_id;

    UPDATE opportunity_scores
    SET is_current = false
    WHERE opportunity_id = v_job.opportunity_id
      AND user_intelligence_profile_id = v_job.user_intelligence_profile_id
      AND is_current;

    INSERT INTO opportunity_scores (
        opportunity_id,
        user_intelligence_profile_id,
        score_type,
        score_value,
        score_source,
        scoring_version,
        is_current,
        calculated_at
    )
    VALUES
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'opportunity_score', v_opportunity_score, 'rule_engine', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now()),
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'fit_score', COALESCE(v_fit_score, 0), 'ai_analysis', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now()),
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'difficulty_score', COALESCE(v_difficulty_score, 0), 'ai_analysis', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now()),
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'income_potential_score', COALESCE(v_income_potential_score, 0), 'ai_analysis', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now()),
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'probability_to_win_score', COALESCE(v_probability_to_win_score, 0), 'ai_analysis', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now()),
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'urgency_score', COALESCE(v_urgency_score, 0), 'ai_analysis', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now()),
        (v_job.opportunity_id, v_job.user_intelligence_profile_id, 'skills_match_score', COALESCE(v_skills_match_score, 0), 'ai_analysis', COALESCE(NULLIF(trim(p_prompt_version), ''), 'block4-v1'), true, now());

    UPDATE opportunity_analysis_jobs
    SET
        status = 'succeeded',
        last_error_message = NULL,
        last_error_details = NULL,
        completed_at = now(),
        locked_at = NULL,
        locked_by = NULL,
        updated_at = now()
    WHERE id = p_job_id;

    UPDATE opportunities
    SET
        status = 'analyzed',
        updated_at = now()
    WHERE id = v_job.opportunity_id
      AND status IN ('new', 'review_pending');

    RETURN QUERY
    SELECT
        v_analysis_id,
        v_job.opportunity_id,
        v_job.user_intelligence_profile_id,
        v_opportunity_score,
        v_recommended_action;
END;
$$;

CREATE OR REPLACE FUNCTION decision_mark_ai_analysis_failed(
    p_job_id uuid,
    p_error_message text,
    p_error_details jsonb DEFAULT NULL,
    p_retry_delay_minutes integer DEFAULT 30,
    p_max_attempts integer DEFAULT 5
)
RETURNS TABLE (
    job_id uuid,
    job_status text,
    next_attempt_at timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_job opportunity_analysis_jobs%ROWTYPE;
    v_new_status text;
    v_next_attempt_at timestamptz;
BEGIN
    SELECT *
    INTO v_job
    FROM opportunity_analysis_jobs
    WHERE id = p_job_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Analysis job not found: %', p_job_id;
    END IF;

    v_new_status := CASE
        WHEN v_job.attempt_count >= GREATEST(COALESCE(p_max_attempts, 5), 1) THEN 'failed'
        ELSE 'retry'
    END;

    v_next_attempt_at := CASE
        WHEN v_new_status = 'retry' THEN now() + make_interval(mins => GREATEST(COALESCE(p_retry_delay_minutes, 30), 1))
        ELSE now()
    END;

    UPDATE opportunity_analysis_jobs
    SET
        status = v_new_status,
        last_error_message = COALESCE(NULLIF(trim(p_error_message), ''), 'AI decision engine failed without an explicit error message.'),
        last_error_details = p_error_details,
        next_attempt_at = v_next_attempt_at,
        completed_at = CASE WHEN v_new_status = 'failed' THEN now() ELSE NULL END,
        locked_at = NULL,
        locked_by = NULL,
        updated_at = now()
    WHERE id = p_job_id;

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
        'ai-decision-engine',
        CASE
            WHEN v_new_status = 'failed' THEN 'error'
            ELSE 'warning'
        END,
        'opportunity_analysis_failed',
        format('AI decision failed for job %s', p_job_id),
        jsonb_build_object(
            'job_id', p_job_id,
            'opportunity_id', v_job.opportunity_id,
            'user_intelligence_profile_id', v_job.user_intelligence_profile_id,
            'attempt_count', v_job.attempt_count,
            'job_status', v_new_status,
            'error_message', COALESCE(NULLIF(trim(p_error_message), ''), 'AI decision engine failed without an explicit error message.'),
            'error_details', COALESCE(p_error_details, '{}'::jsonb)
        ),
        p_job_id::text,
        now()
    );

    RETURN QUERY
    SELECT
        p_job_id,
        v_new_status,
        v_next_attempt_at;
END;
$$;

COMMIT;
