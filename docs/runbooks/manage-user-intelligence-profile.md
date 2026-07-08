# Runbook - Manage User Intelligence Profile

## Purpose

Block 4 stores AI decision preferences in PostgreSQL, not in source code.

The supported management path is the SQL helper:

- `decision_upsert_user_intelligence_profile(...)`

## Recommended Process

1. Ensure the target `users.id` already exists.
2. Execute the helper function in PostgreSQL with the real profile values.
3. Keep `status = 'active'` only for the profile that should drive the current workflow.
4. Update `scoring_policy` when you need different score weights or action thresholds without changing workflow code.

## Editable Fields

- `core_skills`
- `technology_stack`
- `preferred_project_types`
- `undesirable_project_types`
- `minimum_project_budget`
- `preferred_currency`
- `english_level`
- `experience_level`
- `include_keywords`
- `exclude_keywords`
- `priority_directions`
- `additional_preferences`
- `scoring_policy`

## Example Execution Pattern

Use the helper directly from your PostgreSQL client:

```sql
SELECT *
FROM decision_upsert_user_intelligence_profile(
    p_user_id := '<real-user-uuid>'::uuid,
    p_profile_slug := '<profile-slug>',
    p_status := '<draft-or-active>',
    p_core_skills := ARRAY['<core-skill-1>', '<core-skill-2>'],
    p_technology_stack := ARRAY['<technology-1>', '<technology-2>'],
    p_preferred_project_types := ARRAY['<preferred-type-1>', '<preferred-type-2>'],
    p_undesirable_project_types := ARRAY['<undesirable-type-1>', '<undesirable-type-2>'],
    p_minimum_project_budget := <minimum-budget>,
    p_preferred_currency := '<currency-code>',
    p_english_level := '<english-level>',
    p_experience_level := '<experience-level>',
    p_include_keywords := ARRAY['<keyword-1>', '<keyword-2>'],
    p_exclude_keywords := ARRAY['<negative-keyword-1>', '<negative-keyword-2>'],
    p_priority_directions := ARRAY['<priority-direction-1>', '<priority-direction-2>'],
    p_additional_preferences := '<json-object>'::jsonb,
    p_scoring_policy := '{
        "scoring_weights": {
            "fit_score": 30,
            "skills_match_score": 20,
            "probability_to_win_score": 20,
            "income_potential_score": 15,
            "urgency_score": 10,
            "difficulty_inverse_score": 5
        },
        "thresholds": {
            "apply_now": 80,
            "review_manually": 65,
            "watchlist": 50
        }
    }'::jsonb
);
```

Replace every placeholder with the real user profile before execution.
