# Database Design - Block 2

## Purpose

Block 2 introduces the first production-ready PostgreSQL data model for AI Career Agent. The schema is intentionally focused on durable storage, traceability, deduplication, and future extensibility.

PostgreSQL remains the source of truth. n8n remains an orchestration layer. Google Sheets remains a lightweight journal target and is not treated as a primary datastore.

## V1 Tables

### `users`

Stores the primary user record for the future owner or owners of the system.

Why it exists:

- keeps identity separate from profile metadata
- allows notification ownership and future multi-user expansion
- supports lifecycle state tracking

### `user_profiles`

Stores profile-level career context attached one-to-one to a user.

Why it exists:

- isolates mutable profile details from core identity
- leaves room for later expansion without rewriting `users`
- uses `profile_data` as controlled JSONB for future profile attributes that are not stable enough for V1 normalization

### `sources`

Defines the discovery or ingestion source catalog.

Why it exists:

- centralizes source identity and enablement state
- stores `config_reference` instead of secrets
- tracks latest success and failure timestamps without storing secrets in SQL

### `opportunities`

Stores canonical opportunity records. This is the core business table in the V1 data layer.

Why it exists:

- consolidates all earning opportunities in one normalized table
- keeps source provenance through both `source_id` and snapshot field `source_type`
- supports deduplication through `duplicate_hash`
- supports direct-source uniqueness through `(source_id, external_id)`

### `opportunity_ai_analysis`

Stores qualitative AI analysis snapshots per opportunity.

Why it exists:

- keeps narrative analysis separate from the base opportunity record
- supports repeated analysis runs over time through append-only history
- uses `is_current` to mark the active analysis without deleting history

### `opportunity_scores`

Stores normalized scoring entries per opportunity and score type.

Why it exists:

- separates operational ranking data from AI narrative text
- supports multiple score dimensions and versioned scoring history
- allows future rule-based and manual scoring without redesigning the schema

### `notifications`

Stores future notification intents and delivery state.

Why it exists:

- keeps outbound delivery tracking in PostgreSQL
- avoids coupling future Telegram or email delivery status to workflow state alone
- allows retries, failure diagnostics, and auditability later

### `google_sheets_journal`

Stores the contract-ready journal payload for future Google Sheets writes.

Why it exists:

- prepares the future Sheets integration without making Sheets a system of record
- keeps a lightweight append-oriented export contract in the database
- allows later workflow delivery to read from a stable structure

V1 contract columns:

- `date`
- `source`
- `opportunity_type`
- `title`
- `score`
- `status`
- `url`

These map directly to the intended lightweight Google Sheets journal concept. Real integration is intentionally out of scope for Block 2.

### `source_run_logs`

Stores ingestion or collection run telemetry for each source.

Why it exists:

- records source execution outcome
- stores processing and save counters
- supports future monitoring, troubleshooting, and SLA reporting

### `system_logs`

Stores structured application-level or workflow-level operational events.

Why it exists:

- provides a durable structured log sink for important business or orchestration events
- supports severity-based filtering and correlation IDs
- separates high-value persisted logs from ephemeral container logs

## Main Relationships

- `user_profiles.user_id -> users.id`
- `opportunities.source_id -> sources.id`
- `opportunity_ai_analysis.opportunity_id -> opportunities.id`
- `opportunity_scores.opportunity_id -> opportunities.id`
- `notifications.user_id -> users.id`
- `notifications.opportunity_id -> opportunities.id`
- `google_sheets_journal.opportunity_id -> opportunities.id`
- `source_run_logs.source_id -> sources.id`

## Why This Structure Was Chosen

### PostgreSQL owns business truth

Opportunities, analysis snapshots, scores, notifications, and run telemetry are persisted in PostgreSQL instead of being delegated to n8n or Google Sheets. This preserves consistency, queryability, and future API readiness.

### Core records and derived records are separated

`opportunities` stores the canonical source-derived record. AI analysis, scoring, notification state, and journaling are modeled as adjacent tables rather than extra columns on the main table. This keeps the model easier to evolve and prevents the central opportunity record from becoming a write hotspot for unrelated concerns.

### Deduplication is explicit

The schema uses both:

- a unique `duplicate_hash` for normalized content-level deduplication
- a unique partial index on `(source_id, external_id)` when the source gives a stable external identifier

This gives stronger protection than relying on URLs or titles alone.

### History is preserved where it matters

AI analysis and scoring are modeled to allow repeated recalculation over time. The `is_current` partial unique indexes provide a stable "latest active" record without destroying historical context.

### Google Sheets stays lightweight

The journal table is intentionally small and export-oriented. It exists to support future append-style reporting and visibility, not primary storage.

## Indexing Strategy

The schema adds indexes for:

- identity lookups such as normalized user email
- source and status filtering on opportunities
- deduplication on opportunities
- current AI analysis and current score retrieval
- notification delivery queue access
- source run telemetry lookups
- system log filtering by source, severity, and time

## What Will Expand In Later Blocks

The following are intentionally left for later blocks:

- source-specific ingestion payload storage and connectors
- real AI execution flows and prompt/result orchestration
- actual Telegram delivery flows
- application tracking and CRM-like follow-up entities
- richer user preference normalization
- source-specific config schemas
- materialized reporting views or rollups

## Migration Files

V1 is delivered through:

- `database/migrations/20260708141000__create_v1_core_tables.sql`
- `database/migrations/20260708141100__create_v1_indexes.sql`
- `database/migrations/20260708141200__create_v1_updated_at_triggers.sql`
- `database/migrations/20260708153000__add_block3_collection_functions.sql`

## Block 3 Collection Helpers

Block 3 adds database-side helpers so every source branch uses one persistence path:

- `collection_ensure_source(...)`
- `collection_upsert_opportunity(...)`
- `collection_ingest_source_batch(...)`

This keeps deduplication, run logging, and final storage consistent across RSS and HeadHunter connectors.

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

This starts a temporary PostgreSQL container, applies all migrations in order, runs `database/sql/verify_v1_schema.sql`, and removes the container afterward unless told otherwise.
