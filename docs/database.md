# Database Design

## Purpose

The PostgreSQL model is intentionally focused on durable storage, traceability, deduplication, AI auditability, and future extensibility.

PostgreSQL is the source of truth. n8n is an orchestration layer. Google Sheets is prepared only as a future lightweight export target and is not treated as a primary datastore.

## Current Tables

### `users`

Stores the primary user record.

### `user_profiles`

Stores broad profile-level career context attached one-to-one to a user.

### `user_intelligence_profiles`

Stores the machine-readable preference set used by the AI decision engine.

Why it exists:

- separates operational AI preference logic from the broader human profile layer
- makes the profile editable through PostgreSQL without code changes
- stores both preference fields and scoring-policy overrides in one governed entity

### `sources`

Stores the controlled source catalog for opportunity collection.

### `opportunities`

Stores canonical opportunity records with deduplication metadata.

### `opportunity_analysis_jobs`

Stores durable AI analysis queue state per opportunity/profile pair.

Why it exists:

- prevents duplicate work during overlapping workflow runs
- supports retry logic without relying on ephemeral n8n execution state
- tracks attempts, lock ownership, and last failure reason

### `opportunity_ai_analysis`

Stores qualitative AI analysis snapshots per opportunity and per user intelligence profile.

Why it exists:

- keeps narrative analysis separate from the base opportunity record
- supports repeated analysis runs over time through append-only history
- stores provider metadata, fit and non-fit explanations, and audit snapshots

### `opportunity_scores`

Stores normalized scoring entries per opportunity, per user intelligence profile, and per score type.

Why it exists:

- separates ranking data from qualitative AI narrative text
- supports multiple score dimensions and versioned scoring history
- allows rule-based final scoring without redesigning the schema

### `notifications`

Stores future notification intents and delivery state.

### `google_sheets_journal`

Stores the future export contract for Google Sheets journaling.

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
- `google_sheets_journal.opportunity_id -> opportunities.id`
- `source_run_logs.source_id -> sources.id`

## Why This Structure Was Chosen

### PostgreSQL owns business truth

Opportunities, AI queue state, analysis snapshots, scores, notifications, and telemetry are persisted in PostgreSQL instead of being delegated to n8n.

### Core records and derived records are separated

`opportunities` stores the canonical source-derived record. Queue state, AI analysis, scoring, notification state, and journaling are modeled as adjacent tables to reduce coupling and preserve history.

### User intelligence is separated from the generic profile

`user_profiles` remains the broad human-facing profile layer. `user_intelligence_profiles` is optimized for AI decision input and configurable scoring policy. This avoids mixing unstable machine-facing preferences into the general profile table.

### Deduplication is explicit

The schema uses both:

- a unique `duplicate_hash` for normalized content-level deduplication
- a unique partial index on `(source_id, external_id)` when the source provides a stable identifier

### History is preserved where it matters

AI analysis and scoring allow repeated recalculation over time. The `is_current` partial unique indexes keep a stable active record for each opportunity/profile pair without destroying history.

### AI queue state is durable

`opportunity_analysis_jobs` keeps claim and retry state in PostgreSQL. This was chosen instead of relying on workflow execution memory so that AI retries, profile edits, and overlapping schedules stay observable and recoverable.

## Indexing Strategy

The schema adds indexes for:

- identity lookups
- source and status filtering on opportunities
- deduplication on opportunities
- current AI analysis and current score retrieval per profile
- analysis queue claim and retry retrieval
- notification delivery queue access
- source run telemetry lookups
- system log filtering by source, severity, and time

## Workflow Support Functions

### Block 3 Collection Helpers

- `collection_ensure_source(...)`
- `collection_upsert_opportunity(...)`
- `collection_ingest_source_batch(...)`

These helpers keep collection persistence, deduplication, and run logging consistent across connectors.

### Block 4 Decision Helpers

- `decision_upsert_user_intelligence_profile(...)`
- `decision_calculate_opportunity_score(...)`
- `decision_determine_recommended_action(...)`
- `decision_claim_analysis_batch(...)`
- `decision_record_ai_analysis(...)`
- `decision_mark_ai_analysis_failed(...)`

These helpers keep the queue, scoring logic, retries, and persistence contract in PostgreSQL instead of inside the workflow.

## Migration Files

Current migrations:

- `database/migrations/20260708141000__create_v1_core_tables.sql`
- `database/migrations/20260708141100__create_v1_indexes.sql`
- `database/migrations/20260708141200__create_v1_updated_at_triggers.sql`
- `database/migrations/20260708153000__add_block3_collection_functions.sql`
- `database/migrations/20260708170000__add_block4_ai_decision_engine.sql`

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
