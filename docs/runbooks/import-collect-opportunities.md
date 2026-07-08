# Runbook - Import Collect Opportunities Workflow

## Goal

Import the Block 3 workflow into n8n without changing production infrastructure unexpectedly.

## Files

- workflow: `n8n/workflows/collect-opportunities.json`
- source contract: `config/n8n/collect-opportunities.sources.json`

## Required Credentials In n8n

- PostgreSQL credential for the AI Career Agent database

No HeadHunter credential is required for the current public vacancies endpoint workflow branch.

Telegram credential is intentionally not required in Block 3 because the Telegram collector is not activated.

## Import Steps

1. Open n8n.
2. Import `n8n/workflows/collect-opportunities.json`.
3. Attach the PostgreSQL credential to every Postgres node in the workflow.
4. Review source URLs and, if needed, override them through environment variables.
5. Run the workflow manually once.
6. Verify:
   - new rows appear in `opportunities`
   - source runs appear in `source_run_logs`
   - failures, if any, appear in `system_logs`

## Optional Environment Overrides

- `COLLECT_RSS_WWR_URL`
- `COLLECT_RSS_REMOTEOK_URL`
- `COLLECT_HH_AUTOMATION_URL`
- `COLLECT_HH_OPENAI_URL`

## Post-Import Check

Recommended SQL verification targets:

- `SELECT count(*) FROM opportunities;`
- `SELECT source_id, run_status, processed_count, saved_count, skipped_count, run_started_at FROM source_run_logs ORDER BY run_started_at DESC LIMIT 20;`
- `SELECT severity, event_type, message, occurred_at FROM system_logs ORDER BY occurred_at DESC LIMIT 20;`
