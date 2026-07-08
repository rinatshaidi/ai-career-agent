# Runbook - Configure Google Sheets Feedback Archive

## Purpose

This runbook prepares the Google Sheets archive used by Block 6.

## Required Header Row

Create the target sheet and set the first row to:

1. `archive_key`
2. `date`
3. `source`
4. `opportunity_type`
5. `title`
6. `score`
7. `ai_recommendation`
8. `user_action`
9. `result`
10. `url`

## Why `archive_key` Is Required

`archive_key` is the deterministic row identity.

Without it, repeated actions such as:

- `saved` -> `applied`
- `applied` -> `got_project`
- `applied` -> `rejected`

would append duplicates instead of updating one long-lived archive row.

## Environment Variables

- `GOOGLE_SHEETS_ARCHIVE_DOCUMENT_ID`
- `GOOGLE_SHEETS_ARCHIVE_SHEET_NAME`

## Credential Assignment

Use the existing production Google Sheets credentials already available in n8n.

Do not commit credential payloads into the repository export.

## Validation

After one real Telegram feedback action:

1. Check that the row exists in PostgreSQL:

```sql
SELECT archive_key, sync_status, user_action, result
FROM google_sheets_journal
ORDER BY updated_at DESC
LIMIT 10;
```

2. Confirm that the same `archive_key` row exists in Google Sheets.
3. Trigger another action for the same opportunity and confirm the same row is updated instead of duplicated.
