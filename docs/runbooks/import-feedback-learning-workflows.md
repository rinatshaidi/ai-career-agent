# Runbook - Import Feedback Learning Workflows

## Purpose

This runbook imports the Block 6 feedback workflows into n8n without committing secrets.

## Files

- `n8n/workflows/handle-opportunity-notification-actions.json`
- `n8n/workflows/maintain-working-memory-retention.json`

## Steps

1. Apply all PostgreSQL migrations before importing the workflows.
2. In n8n, import `handle-opportunity-notification-actions.json`.
3. Assign the existing PostgreSQL credentials to every Postgres node in the workflow.
4. Assign the existing Google Sheets OAuth2 credentials to `Google Sheets | Upsert Archive`.
5. Import `maintain-working-memory-retention.json`.
6. Assign the existing PostgreSQL credentials to `Purge Expired Working Memory`.
7. Set environment variables:
   - `TELEGRAM_INLINE_ACTIONS_ENABLED=true`
   - `GOOGLE_SHEETS_ARCHIVE_DOCUMENT_ID`
   - `GOOGLE_SHEETS_ARCHIVE_SHEET_NAME`
   - `WORKING_MEMORY_RETENTION_DAYS=60`
8. Expose the callback webhook route and connect it to the Telegram bot update delivery.
9. Keep both workflows inactive until PostgreSQL access, Telegram webhook delivery, and Google Sheets access are verified.
10. Activate the callback workflow first, then activate the Telegram delivery workflow, then activate the retention workflow.

## Verification

1. Send one real opportunity through `Send Opportunity Notifications`.
2. Press one inline action button in Telegram.
3. Confirm:
   - a row exists in `user_feedback_history`
   - a row exists in `learning_feedback_dataset`
   - the notification has updated feedback metadata
   - the opportunity status changed as expected
   - the Google Sheets row was created or updated by `archive_key`

## Useful SQL

```sql
SELECT feedback_action_key, ai_recommendation, result, recorded_at
FROM user_feedback_history
ORDER BY recorded_at DESC
LIMIT 20;
```

```sql
SELECT archive_key, ai_recommendation, user_action, result, sync_status, last_synced_at
FROM google_sheets_journal
ORDER BY updated_at DESC
LIMIT 20;
```

```sql
SELECT user_action, result, recommendation_success, source_name, project_type, captured_at
FROM learning_feedback_dataset
ORDER BY captured_at DESC
LIMIT 20;
```
