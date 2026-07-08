# Architecture - AI Career Agent

## Architecture Principles

- Separation of concerns before feature delivery
- PostgreSQL as the source of truth for business state
- n8n as an orchestration layer, not a substitute for domain ownership
- Configuration and secrets separated from source code
- Incremental scalability without forced rewrites
- Provider-specific AI execution isolated from scoring and persistence rules

## Chosen Repository Model

The project uses a modular monorepo foundation.

This remains the most professional choice because it gives the project a single source of truth for application code, workflow artifacts, database assets, scripts, and documentation while still preserving clean internal boundaries.

## High-Level System Layers

### 1. Application Layer

Reserved under `apps/`.

- `apps/api/` is intended for the future synchronous application boundary.
- `apps/worker/` is intended for future asynchronous workloads.

No backend API or worker business logic is introduced in Block 4.

### 2. Shared Contracts Layer

Reserved under `packages/shared/`.

This layer is prepared for future schemas, DTOs, validation logic, and reusable utilities once executable services appear.

### 3. Data Layer

- `database/migrations/` is the only place for schema evolution scripts.
- `database/sql/` stores verification SQL and curated operational statements.

Current responsibility split:

- `users` and `user_profiles` store user identity and broad profile context
- `user_intelligence_profiles` stores the editable machine-readable decision profile used by the AI engine
- `sources` stores the controlled catalog of ingestion sources
- `opportunities` stores the canonical opportunity record and deduplication metadata
- `opportunity_analysis_jobs` stores durable AI queue, retry, and lock state
- `opportunity_ai_analysis` stores append-only per-profile AI analysis snapshots
- `opportunity_scores` stores normalized per-profile score history by score type
- `notifications` stores future outbound notification state
- `google_sheets_journal` stores the future lightweight export contract
- `source_run_logs` and `system_logs` store structured operational telemetry

The data layer separates canonical records from derived records. Opportunities remain the central source-derived entity, while queue state, analysis, scoring, notifications, and journaling are modeled in adjacent tables to preserve history and reduce coupling.

### 4. Automation Layer

Reserved under `n8n/`.

- `n8n/workflows/` is for source-controlled workflow definitions.
- `n8n/exports/` is for versioned exports or handoff artifacts when needed.

n8n is positioned as the automation and integration runtime. It coordinates workflows, triggers actions, and integrates systems, but persistent business state remains owned by PostgreSQL.

Current maintained workflows:

- `Collect Opportunities`
- `Analyze Opportunities`

The first workflow collects and normalizes source data. The second workflow claims queued opportunities, calls OpenAI, parses the structured response, and persists the result through PostgreSQL helper functions.

### 5. Configuration Layer

Reserved under `config/` and root environment files.

This layer groups configuration by concern:

- `config/env/` for environment-specific templates and conventions
- `config/docker/` for future compose overrides or container-related assets
- `config/n8n/` for workflow governance artifacts, contracts, and runtime notes

Secrets are never committed to the repository.

## Runtime Strategy

The future primary implementation runtime remains Node.js LTS with TypeScript.

This keeps build, lint, test, and deployment pipelines simpler while still fitting API orchestration, integrations, and future application services. The architecture stays intentionally scalable without becoming prematurely polyglot.

## Docker Compose Strategy

The root `docker-compose.yml` remains a safe local-stack baseline, not a production deployment manifest.

Key decisions:

- services are behind an optional `local-infra` profile
- existing infrastructure is not modified by the repository
- the file acts as a controlled starting point for isolated local bring-up when a later block requires it

## Data And Ownership Boundaries

- Business state belongs in PostgreSQL.
- Workflow execution state belongs in n8n only where required by n8n itself.
- Shared contracts belong in `packages/shared/`.
- Operational scripts belong in `scripts/`.
- Documentation and decisions belong in `docs/`.

For collection specifically:

- source-specific fetch logic lives in n8n connector branches
- source normalization happens before persistence
- deduplication and final persistence happen in PostgreSQL helper functions
- source failures are logged per branch

For AI decisioning specifically:

- editable user preference state lives in `user_intelligence_profiles`
- claim, lock, retry, and replay state live in `opportunity_analysis_jobs`
- provider-specific prompt and HTTP execution live in the workflow
- final Opportunity Score and action thresholds live in PostgreSQL helper functions
- analysis history remains append-only through `opportunity_ai_analysis` and `opportunity_scores`

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

## Current Scope Boundary

The architecture currently includes:

- PostgreSQL schema and migration assets
- source collection through n8n
- unified Opportunity normalization
- deduplicated persistence and operational source logging
- OpenAI-backed AI decisioning with per-profile persistence and deterministic final scoring

The architecture intentionally still does not implement:

- Telegram notifications
- Google Sheets journaling
- backend APIs
- web interface
- worker services outside n8n
