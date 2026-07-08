# Database Design

## Purpose

The PostgreSQL model is intentionally focused on durable storage, traceability, deduplication, AI auditability, delivery idempotency, and future extensibility.

PostgreSQL is the source of truth. n8n is an orchestration layer. Google Sheets is treated as a long-lived archive target, but not as a primary datastore.

## Current Tables

### `users`

Stores the primary user record.

### `user_profiles`

Stores broad profile-level career context attached one-to-one to a user.

Block 5 additionally uses `user_profiles.profile_data.telegram_delivery` as the Telegram routing contract for:

- `chat_id`
- `enabled`
- `bot_name`

### `user_intelligence_profiles`

Stores the machine-readable preference set used by the AI decision engine.

### `sources`

Stores the controlled source catalog for opportunity collection.

### `opportunities`

Stores canonical opportunity records with deduplication metadata.

### `opportunity_analysis_jobs`

Stores durable AI analysis queue state per opportunity/profile pair.

### `opportunity_ai_analysis`

Stores qualitative AI analysis snapshots per opportunity and per user intelligence profile.

### `opportunity_scores`

Stores normalized scoring entries per opportunity, per user intelligence profile, and per score type.

### `notifications`

Stores the delivery outbox and notification execution state.

Why it exists:

- prevents duplicate Telegram sends for the same opportunity/profile
- keeps retry state outside transient workflow memory
- stores durable send status, lock state, attempt counters, payload snapshots, and the latest feedback summary during the working-memory lifetime

### `google_sheets_journal`

Stores the durable Google Sheets archive-sync contract.

Block 6 expands this table with:

- `archive_key`
- `ai_recommendation`
- `user_action`
- `result`
- `sync_status`
- sync timestamps and error fields

This table now survives the 60-day working-memory purge.

### `feedback_action_catalog`

Stores the supported user feedback actions and their lifecycle effects.

### `user_feedback_history`

Stores append-only user feedback events with an idempotency key.

### `learning_feedback_dataset`

Stores the future model-training dataset separately from `opportunities`.

### `source_run_logs`

Stores collection run telemetry per source.

### `system_logs`

Stores structured application-level and workflow-level operational events.

## Main Relationships

- `user_profiles.user_id -> users.id`
- `user_intelligence_profiles.user_id -> users.id`
- `opportunities.source_id -> sources.id`
- `opportunity_analysis_jobs.opportunity_id -> opportunities.id`
- `opportunity_analysis_jobs.user_intelligence_profile_id -> user_intelligence_profiles.id`
- `opportunity_ai_analysis.opportunity_id -> opportunities.id`
- `opportunity_ai_analysis.user_intelligence_profile_id -> user_intelligence_profiles.id`
- `opportunity_scores.opportunity_id -> opportunities.id`
- `opportunity_scores.user_intelligence_profile_id -> user_intelligence_profiles.id`
- `notifications.user_id -> users.id`
- `notifications.opportunity_id -> opportunities.id`
- `notifications.user_intelligence_profile_id -> user_intelligence_profiles.id`
- `user_feedback_history.user_id -> users.id`
- `user_feedback_history.user_intelligence_profile_id -> user_intelligence_profiles.id`
- `user_feedback_history.notification_id -> notifications.id`
- `user_feedback_history.opportunity_id -> opportunities.id`
- `learning_feedback_dataset.feedback_history_id -> user_feedback_history.id`
- `google_sheets_journal.notification_id -> notifications.id`
- `google_sheets_journal.opportunity_id -> opportunities.id`
- `source_run_logs.source_id -> sources.id`

## Why This Structure Was Chosen

### PostgreSQL owns business truth

Opportunities, AI queue state, analysis snapshots, scores, delivery state, and telemetry are persisted in PostgreSQL instead of being delegated to n8n.

### Core records and derived records are separated

`opportunities` stores the canonical source-derived record. Queue state, AI analysis, scoring, notification state, feedback history, learning history, and archive sync state are modeled as adjacent tables to reduce coupling and preserve history.

### User intelligence is separated from the generic profile

`user_profiles` remains the broad human-facing profile layer and also holds delivery routing metadata. `user_intelligence_profiles` stays focused on AI decision input and scoring policy.

### Delivery and feedback are idempotent

Telegram delivery uses the existing `notifications` table as an outbox with a unique key for the user/profile/opportunity combination. This prevents repeated sends even if the workflow runs again.

Feedback events are idempotent through `user_feedback_history.idempotency_key`, which is derived from the real Telegram callback identity when available.

### AI queue state, delivery queue state, and learning evidence are separated

`opportunity_analysis_jobs` and `notifications` keep retry and lock state in PostgreSQL so that workflow restarts do not lose operational state, while `user_feedback_history`, `learning_feedback_dataset`, and `google_sheets_journal` preserve long-lived evidence beyond the 60-day working-memory retention window.

## Indexing Strategy

The schema adds indexes for:

- identity lookups
- source and status filtering on opportunities
- current AI analysis and current score retrieval per profile
- analysis queue claim and retry retrieval
- notification delivery queue claim, lock recovery, and idempotency
- Google Sheets archive row uniqueness per `archive_key`
- feedback-history and learning-dataset lookups
- source run telemetry lookups
- system log filtering by source, severity, and time

## Workflow Support Functions

### Block 3 Collection Helpers

- `collection_ensure_source(...)`
- `collection_upsert_opportunity(...)`
- `collection_ingest_source_batch(...)`

### Block 4 Decision Helpers

- `decision_upsert_user_intelligence_profile(...)`
- `decision_calculate_opportunity_score(...)`
- `decision_determine_recommended_action(...)`
- `decision_claim_analysis_batch(...)`
- `decision_record_ai_analysis(...)`
- `decision_mark_ai_analysis_failed(...)`

### Block 5 Delivery Helpers

- `delivery_upsert_telegram_target(...)`
- `delivery_sync_telegram_outbox(...)`
- `delivery_claim_notification_batch(...)`
- `delivery_mark_notification_sent(...)`
- `delivery_mark_notification_failed(...)`
- `delivery_record_notification_action(...)`

### Block 6 Feedback Helpers

- `feedback_normalize_project_type(...)`
- `feedback_extract_matched_technologies(...)`
- `feedback_record_notification_action(...)`
- `feedback_mark_google_sheet_archive_synced(...)`
- `feedback_mark_google_sheet_archive_failed(...)`
- `feedback_purge_expired_working_memory(...)`

These helpers keep Telegram eligibility, outbox state, feedback capture, archive sync state, learning dataset assembly, and retention logic in PostgreSQL instead of in workflow-local logic.

## Migration Files

Current migrations:

- `database/migrations/20260708141000__create_v1_core_tables.sql`
- `database/migrations/20260708141100__create_v1_indexes.sql`
- `database/migrations/20260708141200__create_v1_updated_at_triggers.sql`
- `database/migrations/20260708153000__add_block3_collection_functions.sql`
- `database/migrations/20260708170000__add_block4_ai_decision_engine.sql`
- `database/migrations/20260708183000__add_block5_telegram_delivery_engine.sql`
- `database/migrations/20260708203000__add_block6_feedback_learning_engine.sql`
- `database/migrations/20260708220000__fix_block65_production_integration_gaps.sql`

## Validation Approach

To validate migrations without touching production infrastructure:

1. Run the static validator:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

2. If Docker is available locally, run the disposable database validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode docker
```

This starts a temporary PostgreSQL container, applies all migrations in order, runs every verification SQL file under `database/sql/`, and removes the container afterward unless told otherwise.

The Block 6.5 corrective migration intentionally preserves immutable migration history: the original Block 5 migration remains unchanged, while the later migration overrides the effective Telegram fallback name to `Ri Career Agent` and updates existing stored profile metadata where the earlier fallback had already been persisted.
