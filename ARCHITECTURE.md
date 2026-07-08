# Architecture - AI Career Agent

## Architecture Principles

- Separation of concerns before feature delivery
- PostgreSQL as the source of truth for business state
- n8n as an orchestration layer, not a substitute for domain ownership
- Configuration and secrets separated from source code
- Incremental scalability without forced rewrites
- Provider-specific AI execution isolated from scoring and persistence rules
- Delivery transport isolated from AI decision state

## Chosen Repository Model

The project uses a modular monorepo foundation.

This remains the most professional choice because it gives the project a single source of truth for application code, workflow artifacts, database assets, scripts, and documentation while still preserving clean internal boundaries.

## High-Level System Layers

### 1. Application Layer

Reserved under `apps/`.

- `apps/api/` is intended for the future synchronous application boundary.
- `apps/worker/` is intended for future asynchronous workloads.

No backend API or worker business logic is introduced in Block 5.

### 2. Shared Contracts Layer

Reserved under `packages/shared/`.

This layer is prepared for future schemas, DTOs, validation logic, and reusable utilities once executable services appear.

### 3. Data Layer

- `database/migrations/` is the only place for schema evolution scripts.
- `database/sql/` stores verification SQL and curated operational statements.

Current responsibility split:

- `users` and `user_profiles` store user identity, broad profile context, and Telegram delivery target metadata
- `user_intelligence_profiles` stores the editable machine-readable decision profile used by the AI engine
- `sources` stores the controlled catalog of ingestion sources
- `opportunities` stores the canonical opportunity record and deduplication metadata
- `opportunity_analysis_jobs` stores durable AI queue, retry, and lock state
- `opportunity_ai_analysis` stores append-only per-profile AI analysis snapshots
- `opportunity_scores` stores normalized per-profile score history by score type
- `notifications` stores the delivery outbox and notification execution state
- `google_sheets_journal` stores the lightweight journal contract for successful deliveries
- `source_run_logs` and `system_logs` store structured operational telemetry

### 4. Automation Layer

Reserved under `n8n/`.

- `n8n/workflows/` is for source-controlled workflow definitions.
- `n8n/exports/` is for versioned exports or handoff artifacts when needed.

n8n coordinates collection, AI analysis, and Telegram delivery, but persistent business state remains owned by PostgreSQL.

Current maintained workflows:

- `Collect Opportunities`
- `Analyze Opportunities`
- `Send Opportunity Notifications`

Prepared callback template:

- `Handle Opportunity Notification Actions`

### 5. Configuration Layer

Reserved under `config/` and root environment files.

This layer groups configuration by concern:

- `config/env/` for environment-specific templates and conventions
- `config/docker/` for future compose overrides or container-related assets
- `config/n8n/` for workflow governance artifacts, contracts, and runtime notes

Secrets are never committed to the repository.

## Runtime Strategy

The future primary implementation runtime remains Node.js LTS with TypeScript.

The current delivery implementation intentionally stays inside PostgreSQL plus n8n to avoid introducing a dedicated delivery service before it is justified by actual scale.

## Docker Compose Strategy

The root `docker-compose.yml` remains a safe local-stack baseline, not a production deployment manifest.

It exposes the environment variables required for collection, AI analysis, and Telegram delivery when a local `n8n` stack is intentionally started.

## Data And Ownership Boundaries

- Business state belongs in PostgreSQL.
- Workflow execution state belongs in n8n only where required by n8n itself.
- Shared contracts belong in `packages/shared/`.
- Operational scripts belong in `scripts/`.
- Documentation and decisions belong in `docs/`.

For collection:

- source-specific fetch logic lives in n8n branches
- normalization happens before persistence
- deduplication and final persistence happen in PostgreSQL helper functions

For AI decisioning:

- editable user preference state lives in `user_intelligence_profiles`
- claim, lock, retry, and replay state live in `opportunity_analysis_jobs`
- provider-specific prompt and HTTP execution live in the workflow
- final Opportunity Score and action thresholds live in PostgreSQL helper functions

For Telegram delivery:

- eligibility remains owned by current PostgreSQL AI analysis state
- `notifications` is the outbox and retry owner
- the workflow only syncs, claims, sends, and reports status
- successful sends append a lightweight row to `google_sheets_journal`
- inline action capture is prepared but deliberately isolated from scoring and learning logic

## Scalability Path

The current structure is ready to support the following later without repository redesign:

- CI/CD pipelines
- image builds and registries
- multi-environment configuration overlays
- schema migrations
- workflow promotion between environments
- structured observability and runbooks
- application test suites by layer
- future API and worker services
- feedback-learning pipelines on top of recorded Telegram actions

## Current Scope Boundary

The architecture currently includes:

- PostgreSQL schema and migration assets
- source collection through n8n
- unified Opportunity normalization
- OpenAI-backed AI decisioning with per-profile persistence and deterministic final scoring
- Telegram delivery through a PostgreSQL-owned outbox
- lightweight Google Sheets journal contract writes after successful delivery

The architecture intentionally still does not implement:

- direct Google Sheets API export
- backend APIs
- web interface
- worker services outside n8n
- full feedback learning or adaptive re-ranking from Telegram actions
