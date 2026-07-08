# AI Career Agent

AI Career Agent is a production-oriented repository for an AI-driven career automation platform. The repository now contains the project foundation, the first PostgreSQL data model, and the first opportunity collection workflow with deduplicated persistence into PostgreSQL.

## Project Goals

- Prepare a scalable repository foundation for further development blocks.
- Separate product logic, automation workflows, database assets, and operational scripts from day one.
- Keep the future system maintainable, auditable, and safe for production growth.
- Preserve existing infrastructure and avoid changes to live services during Block 1.

## Technology Stack

- Primary application runtime: Node.js LTS with TypeScript
- Automation layer: n8n
- System of record: PostgreSQL
- Container orchestration baseline: Docker Compose
- AI provider integration target: OpenAI
- Messaging integration target: Telegram
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
|-- database/
|   |-- migrations/
|   `-- sql/
|-- docs/
|   |-- adr/
|   `-- runbooks/
|-- logs/
|-- n8n/
|   |-- exports/
|   `-- workflows/
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

The repository uses a modular monorepo foundation. `apps/` is reserved for future executable services, `packages/` for reusable contracts and shared modules, `database/` for migration and SQL assets, and `n8n/` for workflow exports and automation artifacts. PostgreSQL is planned as the source of truth, while n8n is treated as an orchestration and integration layer rather than a business-data store.

This separation is intentional. It reduces coupling between workflows, data, and application logic, keeps deployments more predictable, and makes later scaling easier when the project moves beyond a single service.

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

6. Continue development strictly by blocks and keep new decisions documented in `docs/adr/`.

## Development Process

- Block 1 builds the foundation only.
- Block 2 adds the V1 PostgreSQL schema, SQL migrations, and migration validation assets.
- Block 3 adds the first opportunity collection workflow, source contracts, ingestion SQL helpers, and deduplicated persistence into PostgreSQL.
- AI execution and Telegram bot implementation belong to later blocks.
- New SQL changes should go only into `database/migrations/`.
- Schema verification SQL belongs in `database/sql/`.
- Exported n8n workflows should be versioned in `n8n/workflows/` or `n8n/exports/`.
- Operational or validation automation belongs in `scripts/`.
- Test assets should be organized by test layer inside `tests/`.

## Current Status

The repository currently includes:

- Block 1 foundation and project structure
- Block 2 PostgreSQL schema and migration validation assets
- Block 3 opportunity collection workflow for RSS and HeadHunter

AI analysis, scoring, Telegram notifications, Google Sheets journaling, backend APIs, and UI remain intentionally out of scope for the current repository state.
