# AI Career Agent

AI Career Agent is a production-oriented repository for an AI-driven career automation platform. The repository now contains the project foundation, the PostgreSQL source-of-truth schema, opportunity collection, the AI Decision Engine, the Telegram Delivery Engine, and the Feedback & Learning Engine that captures real user feedback, updates the Google Sheets archive, and preserves a durable learning dataset.

## Project Goals

- Prepare a scalable repository foundation for further development blocks.
- Separate product logic, automation workflows, database assets, and operational scripts from day one.
- Keep the system maintainable, auditable, and safe for production growth.
- Preserve existing infrastructure and evolve the platform block by block without unsafe rewrites.
- Keep future LLM-provider replacement possible without changing scoring and persistence business logic.
- Keep Telegram delivery idempotent and subordinate to PostgreSQL decision state.
- Keep user feedback, Google Sheets archiving, and future-learning evidence durable without mixing them into short-lived working memory.

## Technology Stack

- Primary application runtime: Node.js LTS with TypeScript
- Automation layer: n8n
- System of record: PostgreSQL
- Container orchestration baseline: Docker Compose
- AI provider integration target: OpenAI
- Delivery channel: Telegram
- Archive layer: Google Sheets
- Operational scripting: PowerShell

## Repository Structure

```text
.
|-- apps/
|   |-- api/
|   `-- worker/
|-- config/
|   |-- docker/
|   |-- env/
|   `-- n8n/
|       |-- ai-decision-engine.md
|       |-- ai-decision-engine.output-schema.json
|       |-- collect-opportunities.md
|       |-- collect-opportunities.sources.json
|       |-- feedback-learning.md
|       |-- feedback-learning.sheet-columns.json
|       `-- telegram-delivery.md
|-- database/
|   |-- migrations/
|   `-- sql/
|-- docs/
|   |-- adr/
|   |-- runbooks/
|   |-- ai-decision-engine.md
|   |-- database.md
|   |-- feedback-learning-engine.md
|   |-- opportunity-collection.md
|   `-- telegram-delivery-engine.md
|-- logs/
|-- n8n/
|   |-- exports/
|   `-- workflows/
|       |-- analyze-opportunities.json
|       |-- collect-opportunities.json
|       |-- handle-opportunity-notification-actions.json
|       |-- maintain-working-memory-retention.json
|       `-- send-opportunity-notifications.json
|-- packages/
|   `-- shared/
|-- scripts/
|-- tests/
|   |-- architecture/
|   `-- integration/
|-- .env.example
|-- .gitignore
|-- ARCHITECTURE.md
|-- CHANGELOG.md
|-- PRD.md
|-- README.md
`-- docker-compose.yml
```

## Architecture Overview

The repository uses a modular monorepo foundation. `apps/` is reserved for future executable services, `packages/` for reusable contracts, `database/` for migration and SQL assets, and `n8n/` for workflow exports and automation artifacts. PostgreSQL is the source of truth, while n8n is the orchestration layer.

Current block-owned boundaries:

- Block 3 collects and normalizes opportunities into PostgreSQL
- Block 4 evaluates opportunities and writes deterministic AI results into PostgreSQL
- Block 5 reads only current AI-approved opportunities, materializes Telegram outbox rows, delivers them, and updates delivery state
- Block 6 captures Telegram feedback, updates Google Sheets archive rows by `archive_key`, and preserves a separate learning dataset

This keeps AI decisions, delivery idempotency, and audit history in PostgreSQL instead of scattering them across workflows.

## Run Instructions

1. Clone the repository into `C:\codex\ai-career-agent`.
2. Copy `.env.example` to `.env` and fill in environment-specific values.
3. Review `docker-compose.yml`. Local infrastructure remains optional and is not required for migration authoring.
4. Validate the repository structure:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-foundation.ps1
```

5. Validate database migrations without touching production infrastructure:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

6. Validate the collection workflow artifact:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-collection-workflow.ps1
```

7. Validate the AI decision workflow artifact:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-ai-decision-workflow.ps1
```

8. Validate the Telegram delivery workflow artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-telegram-delivery-workflow.ps1
```

9. Validate the feedback and learning workflows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-feedback-learning-workflow.ps1
```

10. Import the maintained workflows only after PostgreSQL migrations are applied and runtime secrets are available in n8n.

## Development Process

- Block 1 builds the foundation only.
- Block 2 adds the V1 PostgreSQL schema, SQL migrations, and migration validation assets.
- Block 3 adds the opportunity collection workflow, source contracts, ingestion SQL helpers, and deduplicated persistence into PostgreSQL.
- Block 4 adds the AI Decision Engine, editable user intelligence profiles, and deterministic final scoring.
- Block 5 adds Telegram delivery through a PostgreSQL-owned outbox.
- Block 6 adds feedback capture, Google Sheets archive sync, and a durable learning dataset with automatic 60-day working-memory retention.
- New SQL changes should go only into `database/migrations/`.
- Schema verification SQL belongs in `database/sql/`.
- Exported n8n workflows should be versioned in `n8n/workflows/` or `n8n/exports/`.
- Operational or validation automation belongs in `scripts/`.
- Architectural decisions should be documented in `docs/adr/`.

## Current Status

The repository currently includes:

- Block 1 foundation and project structure
- Block 2 PostgreSQL schema and migration validation assets
- Block 3 opportunity collection workflow for RSS and HeadHunter
- Block 4 AI Decision Engine workflow, queue-backed OpenAI analysis, and per-profile scoring
- Block 5 Telegram Delivery Engine with durable outbox and retry handling
- Block 6 Feedback & Learning Engine with idempotent Telegram actions, Google Sheets archive updates, and 60-day working-memory retention

Automatic AI retraining, backend APIs, web UI, and dashboards remain intentionally out of scope for the current repository state.
