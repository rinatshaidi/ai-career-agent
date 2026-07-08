# Feedback & Learning Engine - Block 6

## Purpose

Block 6 turns user interaction into durable product data without changing the AI scoring logic.

The engine now:

- captures real Telegram feedback actions
- updates PostgreSQL working memory
- updates a long-lived Google Sheets archive
- stores durable user feedback history
- stores a separate learning dataset for future AI training
- purges short-lived working memory after 60 days

This block does not retrain the AI and does not change the Opportunity Score algorithm.

## Supported User Actions

Supported canonical actions:

- `applied`
- `saved`
- `later`
- `not_interested`
- `already_done`
- `got_project`
- `got_job`
- `rejected`
- `no_response`

The mapping is stored in `feedback_action_catalog`, so new actions can be added through PostgreSQL without redesigning the workflow topology.

## Main Data Flow

1. Telegram callback hits `Handle Opportunity Notification Actions`.
2. PostgreSQL runs `feedback_record_notification_action(...)`.
3. The function records an idempotent feedback event in `user_feedback_history`.
4. The same function updates `notifications` and the coarse `opportunities.status`.
5. A separate row is inserted into `learning_feedback_dataset`.
6. If the AI recommendation is `apply_now` or `review_manually`, the function upserts `google_sheets_journal` with a stable `archive_key`.
7. The workflow upserts the Google Sheets row by `archive_key`.
8. PostgreSQL marks the archive sync as `synced` or `failed`.

## PostgreSQL Model

### `feedback_action_catalog`

Stores the supported action dictionary, lifecycle effect, and learning signal.

### `user_feedback_history`

Stores append-only feedback events.

Why it exists:

- keeps every real user action
- enforces idempotency through `idempotency_key`
- survives the 60-day working-memory purge

### `learning_feedback_dataset`

Stores the future training dataset in a separate table.

Why it exists:

- separates model-training evidence from transient `opportunities`
- preserves AI recommendation, user action, result, technologies, scores, and compact snapshots
- stays queryable after working-memory rows are deleted

### `google_sheets_journal`

From Block 6 onward this table is the durable Google Sheets archive-sync contract.

Important changes:

- the stable upsert key is `archive_key`
- only `apply_now` and `review_manually` are eligible for archive sync
- `watchlist` and `skip` do not create archive rows
- repeated actions update the same archive row instead of appending duplicates

## Google Sheets Contract

Business columns:

- `date`
- `source`
- `opportunity_type`
- `title`
- `score`
- `ai_recommendation`
- `user_action`
- `result`
- `url`

Technical column:

- `archive_key`

Without `archive_key`, idempotent Google Sheets updates are not reliable enough for production use.

## Opportunity Update Strategy

Block 6 intentionally keeps `opportunities.status` coarse to avoid breaking earlier blocks.

Examples:

- `saved` -> `shortlisted`
- `later` -> `review_pending`
- `applied` -> `applied`
- `not_interested`, `rejected`, `no_response` -> `rejected`
- `already_done`, `got_project`, `got_job` -> `archived`

The exact business outcome still lives in feedback history and the learning dataset.

## Learning Dataset Contents

Each row preserves:

- AI recommendation
- user action
- final result
- source
- source type
- opportunity type
- normalized project type
- matched technologies
- score bundle
- budget snapshot
- provider, model, and prompt version
- compact profile and opportunity snapshots

This makes later analytics and future supervised training possible without keeping old `opportunities` forever.

## 60-Day Working Memory Retention

The workflow `Maintain Working Memory Retention` calls `feedback_purge_expired_working_memory(...)`.

Deleted after 60 days:

- `opportunities`
- `opportunity_ai_analysis`
- `opportunity_scores`
- `notifications`
- `source_run_logs`
- `system_logs`

Retained:

- `users`
- `user_intelligence_profiles`
- `feedback_action_catalog`
- `user_feedback_history`
- `learning_feedback_dataset`
- `google_sheets_journal`

## Out Of Scope

Block 6 still does not implement:

- automatic AI retraining
- Web UI
- backend API
- dashboards
- new data sources
