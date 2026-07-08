# AI Decision Engine - Block 4

## Scope

Block 4 introduces the production-ready AI decision layer for AI Career Agent.

The system is responsible for:

- reading canonical `opportunities` from PostgreSQL
- reading the editable `user_intelligence_profiles` entity
- sending opportunity and profile context to OpenAI
- receiving a structured decision payload
- calculating a deterministic overall Opportunity Score
- persisting analysis history, current scores, and retryable job state in PostgreSQL

Block 4 does not implement:

- Telegram delivery
- Google Sheets
- backend API
- web interface
- additional opportunity sources

## User Intelligence Profile

Block 4 introduces a dedicated `user_intelligence_profiles` table instead of overloading the earlier generic `user_profiles` table.

This keeps two concerns separate:

- `user_profiles` remains the broad career or identity profile layer
- `user_intelligence_profiles` becomes the machine-readable decision policy used by the AI engine

Supported fields:

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

The profile can be edited without code through PostgreSQL using `decision_upsert_user_intelligence_profile(...)`.

## Decision Workflow

Maintained workflow:

- `n8n/workflows/analyze-opportunities.json`

Workflow name:

- `Analyze Opportunities`

Execution pattern:

1. claim a batch of analysis jobs through `decision_claim_analysis_batch(...)`
2. build one structured OpenAI request per opportunity
3. parse the strict JSON result
4. persist the result through `decision_record_ai_analysis(...)`
5. if the LLM call fails, mark the job through `decision_mark_ai_analysis_failed(...)`

The queue is stored in PostgreSQL through `opportunity_analysis_jobs`. This avoids duplicate analysis work during overlapping workflow runs and gives the engine durable retry state.

## Opportunity Score

The LLM does not own the final score formula.

OpenAI returns the component scores:

- `fit_score`
- `probability_to_win_score`
- `difficulty_score`
- `income_potential_score`
- `urgency_score`
- `skills_match_score`

PostgreSQL calculates the final `opportunity_score` through `decision_calculate_opportunity_score(...)`.

Default weights:

- fit: `30`
- skills match: `20`
- probability to win: `20`
- income potential: `15`
- urgency: `10`
- inverse difficulty: `5`

Difficulty is inverted inside the formula, so a lower execution difficulty improves the final Opportunity Score.

Final action thresholds are then applied by `decision_determine_recommended_action(...)`:

- `apply_now` at `80+`
- `review_manually` at `65+`
- `watchlist` at `50+`
- otherwise `skip`

These weights and thresholds can be overridden per user through `user_intelligence_profiles.scoring_policy`.

## Replaceability Of The LLM Provider

The OpenAI-specific concern is isolated to the workflow node that performs the HTTP call.

Business logic is intentionally provider-agnostic because:

- profile state lives in PostgreSQL
- job claiming and retry logic live in PostgreSQL
- score calculation and thresholds live in PostgreSQL
- the workflow only has to produce the agreed JSON contract

A future provider replacement therefore changes the provider call and prompt layer, not the scoring or persistence layer.

## Data Persisted By Block 4

- `user_intelligence_profiles`
- `opportunity_analysis_jobs`
- enhanced `opportunity_ai_analysis`
- enhanced `opportunity_scores`
- `system_logs` entries for failed AI jobs

## Validation

Repository-level validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-foundation.ps1
```

Migration-level validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

Workflow validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-ai-decision-workflow.ps1
```
