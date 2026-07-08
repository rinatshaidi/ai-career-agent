# Feedback & Learning Workflow Contract

## Purpose

This contract describes the Block 6 interface between Telegram callback actions, PostgreSQL, and Google Sheets.

The feedback layer does not re-score opportunities and does not retrain the AI model.

Its job is to:

- capture real user actions from Telegram
- update PostgreSQL working memory
- update the long-lived Google Sheets archive
- preserve a durable feedback history
- build a structured learning dataset for future training

## Maintained Workflows

- `n8n/workflows/handle-opportunity-notification-actions.json`
- `n8n/workflows/maintain-working-memory-retention.json`

## PostgreSQL Contracts

### Feedback Tables

- `feedback_action_catalog`
- `user_feedback_history`
- `learning_feedback_dataset`

### Archive Contract Table

- `google_sheets_journal`

From Block 6 onward this table is the durable Google Sheets sync contract, not a delivery-time journal.

### Feedback Functions

- `feedback_normalize_project_type(...)`
- `feedback_extract_matched_technologies(...)`
- `feedback_record_notification_action(...)`
- `feedback_mark_google_sheet_archive_synced(...)`
- `feedback_mark_google_sheet_archive_failed(...)`
- `feedback_purge_expired_working_memory(...)`

## Supported Actions

The Telegram callback workflow supports these canonical action keys:

- `applied`
- `saved`
- `later`
- `not_interested`
- `already_done`
- `got_project`
- `got_job`
- `rejected`
- `no_response`

The action catalog is stored in PostgreSQL so new actions can be added without changing the workflow routing model.

## Google Sheets Archive Rules

Only these AI recommendations are archived to Google Sheets:

- `apply_now`
- `review_manually`

The workflow must not create archive rows for:

- `watchlist`
- `skip`

The stable row key is `archive_key`. Every Google Sheets upsert must match on this column.

## Required Sheet Headers

The expected column order is versioned in:

- `config/n8n/feedback-learning.sheet-columns.json`

Minimal business columns:

- `date`
- `source`
- `opportunity_type`
- `title`
- `score`
- `ai_recommendation`
- `user_action`
- `result`
- `url`

Technical column required for idempotent updates:

- `archive_key`

## Environment Variables

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_API_BASE_URL`
- `TELEGRAM_REQUEST_TIMEOUT_MS`
- `TELEGRAM_INLINE_ACTIONS_ENABLED`
- `GOOGLE_SHEETS_ARCHIVE_DOCUMENT_ID`
- `GOOGLE_SHEETS_ARCHIVE_SHEET_NAME`
- `WORKING_MEMORY_RETENTION_DAYS`

## Retention Boundary

PostgreSQL working memory is automatically purged after `WORKING_MEMORY_RETENTION_DAYS` days.

Block 6 retention removes only:

- `opportunities`
- `opportunity_ai_analysis`
- `opportunity_scores`
- `notifications`
- `source_run_logs`
- `system_logs`

It intentionally keeps:

- `users`
- `user_intelligence_profiles`
- `feedback_action_catalog`
- `user_feedback_history`
- `learning_feedback_dataset`
- `google_sheets_journal`
