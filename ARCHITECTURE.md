# Architecture - AI Career Agent

## Architecture Principles

- Separation of concerns before feature delivery
- PostgreSQL as the future source of truth
- n8n as an orchestration layer, not a substitute for domain ownership
- Configuration and secrets separated from source code
- Incremental scalability without forced rewrites
- Minimal operational complexity in the early stages

## Chosen Repository Model

The project uses a modular monorepo foundation.

This is the most professional choice for Block 1 because it gives the project a single source of truth for application code, workflow artifacts, database assets, scripts, and documentation while still preserving clean internal boundaries. It is more scalable than a flat repo and less operationally expensive than splitting into several repositories too early.

## High-Level System Layers

### 1. Application Layer

Reserved under `apps/`.

- `apps/api/` is intended for the future synchronous application boundary: orchestration endpoints, internal APIs, webhooks, and domain coordination.
- `apps/worker/` is intended for future asynchronous workloads such as queue-driven jobs, AI-heavy processing, and background synchronization.

No business logic is implemented in Block 1.

### 2. Shared Contracts Layer

Reserved under `packages/shared/`.

This layer is prepared for schemas, shared DTOs, event contracts, validation logic, and reusable utilities once application code appears. Keeping it separate prevents cross-service duplication and helps establish stable internal contracts.

### 3. Data Layer

Reserved under `database/`.

- `database/migrations/` is the only place for future schema evolution scripts.
- `database/sql/` is reserved for curated SQL assets such as views, maintenance scripts, or operational queries.

The PostgreSQL schema itself is intentionally not implemented in Block 1.

### 4. Automation Layer

Reserved under `n8n/`.

- `n8n/workflows/` is for source-controlled workflow definitions.
- `n8n/exports/` is for versioned exports or handoff artifacts when needed.

n8n is positioned as the automation and integration runtime. It should coordinate workflows, trigger actions, and integrate systems, but persistent business state should remain owned by PostgreSQL and future application services.

### 5. Configuration Layer

Reserved under `config/` and root environment files.

This layer groups configuration by concern:

- `config/env/` for environment-specific templates and conventions
- `config/docker/` for future compose overrides or container-related assets
- `config/n8n/` for workflow governance artifacts or runtime notes

Secrets are never committed to the repository.

## Runtime Strategy

The future primary implementation runtime is planned as Node.js LTS with TypeScript.

This decision was chosen instead of introducing multiple runtimes in Block 1 because:

- it lowers operational overhead
- it keeps build, lint, test, and deployment pipelines simpler
- it fits well with API orchestration, integrations, and n8n-adjacent services
- it leaves room to introduce a separate specialized runtime later only if justified by actual workload

In other words, the architecture is intentionally scalable without becoming prematurely polyglot.

## Docker Compose Strategy

The root `docker-compose.yml` is prepared as a safe local-stack baseline, not as a production deployment manifest.

Key decisions:

- services are behind an optional `local-infra` profile
- existing infrastructure is not modified by Block 1
- the file serves as a controlled starting point for isolated local bring-up when a later block requires it

This is a better choice than cloning live infrastructure behavior into the repository immediately, because Block 1 must not interfere with already running services.

## Data And Ownership Boundaries

- Future business state belongs in PostgreSQL.
- Future automation state belongs in n8n only where required by n8n itself.
- Shared contracts belong in `packages/shared/`.
- Operational scripts belong in `scripts/`.
- Documentation and decisions belong in `docs/`.

These boundaries reduce long-term confusion about where logic, state, and operational knowledge should live.

## Scalability Path

The current structure is ready to support the following later, without repository redesign:

- CI/CD pipelines
- image builds and registries
- multi-environment configuration overlays
- schema migrations
- workflow promotion between environments
- structured observability and runbooks
- application test suites by layer

## Explicit Block 1 Constraints

The architecture intentionally does not implement:

- opportunity search logic
- AI evaluation logic
- Telegram bot behavior
- PostgreSQL schema
- n8n workflows
- opportunity scoring

Those concerns are acknowledged in the architecture but remain out of scope until later blocks.
