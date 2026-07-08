# Database Design

## Purpose

The PostgreSQL model is intentionally focused on durable storage, traceability, deduplication, AI auditability, delivery idempotency, and future extensibility.

PostgreSQL is the source of truth. n8n is an orchestration layer. Google Sheets remains only a lightweight journal contract target and is not treated as a primary datastore.

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
- stores durable send status, lock state, attempt counters, and payload snapshots

### `google_sheets_journal`

Stores the lightweight journal contract for successful deliveries.

Block 5 adds `notification_id` so one successful notification can map to one journal row idempotently.

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
- `google_sheets_journal.notification_id -> notifications.id`
- `google_sheets_journal.opportunity_id -> opportunities.id`
- `source_run_logs.source_id -> sources.id`

## Why This Structure Was Chosen

### PostgreSQL owns business truth

Opportunities, AI queue state, analysis snapshots, scores, delivery state, and telemetry are persisted in PostgreSQL instead of being delegated to n8n.

### Core records and derived records are separated

`opportunities` stores the canonical source-derived record. Queue state, AI analysis, scoring, notification state, and journaling are modeled as adjacent tables to reduce coupling and preserve history.

### User intelligence is separated from the generic profile

`user_profiles` remains the broad human-facing profile layer and also holds delivery routing metadata. `user_intelligence_profiles` stays focused on AI decision input and scoring policy.

### Delivery is idempotent

Telegram delivery uses the existing `notifications` table as an outbox with a unique key for the user/profile/opportunity combination. This prevents repeated sends even if the workflow runs again.

### AI queue state and delivery queue state are both durable

`opportunity_analysis_jobs` and `notifications` keep retry and lock state in PostgreSQL so that workflow restarts do not lose operational state.

## Indexing Strategy

The schema adds indexes for:

- identity lookups
- source and status filtering on opportunities
- current AI analysis and current score retrieval per profile
- analysis queue claim and retry retrieval
- notification delivery queue claim, lock recovery, and idempotency
- journal row uniqueness per notification
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

These helpers keep Telegram eligibility, outbox state, retries, journal writes, and lightweight callback capture in PostgreSQL instead of in workflow-local logic.

## Migration Files

Current migrations:

- `database/migrations/20260708141000__create_v1_core_tables.sql`
- `database/migrations/20260708141100__create_v1_indexes.sql`
- `database/migrations/20260708141200__create_v1_updated_at_triggers.sql`
- `database/migrations/20260708153000__add_block3_collection_functions.sql`
- `database/migrations/20260708170000__add_block4_ai_decision_engine.sql`
- `database/migrations/20260708183000__add_block5_telegram_delivery_engine.sql`

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
