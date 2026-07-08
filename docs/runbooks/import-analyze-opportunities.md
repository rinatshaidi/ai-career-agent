# Import Runbook - Analyze Opportunities

## Purpose

This runbook describes how to import the Block 4 workflow into n8n without changing committed code or committing credentials.

## Files

- Workflow: `n8n/workflows/analyze-opportunities.json`
- Workflow contract: `config/n8n/ai-decision-engine.md`
- Output schema: `config/n8n/ai-decision-engine.output-schema.json`

## Import Steps

1. Open n8n and choose workflow import from file.
2. Import `n8n/workflows/analyze-opportunities.json`.
3. Assign PostgreSQL access to the Postgres nodes using the existing PostgreSQL credentials.
4. Ensure the workflow can access `OPENAI_API_KEY` and the Block 4 environment variables from the runtime environment.
5. Confirm that at least one active `user_intelligence_profiles` record exists before activation.
6. Run a manual execution to validate database connectivity and OpenAI connectivity.
7. Activate the workflow only after the manual execution completes successfully.

## Required Environment Variables

- `AI_DECISION_PROVIDER`
- `AI_DECISION_PROFILE_SLUG`
- `AI_DECISION_BATCH_SIZE`
- `AI_DECISION_PROMPT_VERSION`
- `AI_DECISION_MODEL`
- `AI_DECISION_RETRY_DELAY_MINUTES`
- `OPENAI_API_BASE_URL`
- `OPENAI_API_KEY`

## Failure Handling

If OpenAI returns an error or an invalid payload:

- the workflow sends the job to `decision_mark_ai_analysis_failed(...)`
- PostgreSQL moves the job into `retry` or `failed`
- a structured `system_logs` entry is written

Other queued opportunities continue independently on later runs.
