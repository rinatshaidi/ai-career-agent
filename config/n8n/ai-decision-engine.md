# AI Decision Engine Workflow Contract

## Purpose

This contract describes the production-ready interface between the n8n workflow and PostgreSQL for Block 4.

The workflow does not own business logic. It is responsible for:

- claiming analysis jobs from PostgreSQL
- building an OpenAI Chat Completions-compatible request for each opportunity
- parsing the structured result
- sending the result back to PostgreSQL helper functions

PostgreSQL remains the owner of:

- editable user intelligence profile state
- analysis job state and retries
- deterministic Opportunity Score calculation
- final recommended action thresholds
- persisted analysis and score history

## Maintained Workflow

- `n8n/workflows/analyze-opportunities.json`

Workflow name:

- `Analyze Opportunities`

## Environment Variables

- `AI_DECISION_PROVIDER`
- `AI_DECISION_PROFILE_SLUG`
- `AI_DECISION_BATCH_SIZE`
- `AI_DECISION_PROMPT_VERSION`
- `AI_DECISION_MODEL`
- `AI_DECISION_RETRY_DELAY_MINUTES`
- `OPENAI_API_BASE_URL`
- `OPENAI_API_KEY`

## Database Helper Functions

- `decision_upsert_user_intelligence_profile(...)`
- `decision_claim_analysis_batch(...)`
- `decision_record_ai_analysis(...)`
- `decision_mark_ai_analysis_failed(...)`
- `decision_calculate_opportunity_score(...)`
- `decision_determine_recommended_action(...)`

## Output Schema

The OpenAI response is expected to conform to:

- `config/n8n/ai-decision-engine.output-schema.json`

Required fields:

- `summary`
- `is_recommended`
- `why_fit`
- `why_not_fit`
- `risks`
- `fit_score`
- `probability_to_win_score`
- `difficulty_score`
- `income_potential_score`
- `urgency_score`
- `skills_match_score`
- `decision_confidence_score`

## Scoring Boundary

The LLM produces the component scores and narrative reasoning.

PostgreSQL calculates the final `opportunity_score` using weighted logic stored in `user_intelligence_profiles.scoring_policy`. This keeps the score formula outside the LLM and keeps business rules provider-agnostic.

Current integration boundary:

- `AI_DECISION_PROVIDER` is persisted as provider metadata and lock context
- the committed HTTP adapter targets OpenAI-compatible chat completions APIs
- a non-compatible provider still requires a workflow adapter change, but not a PostgreSQL business-logic change
