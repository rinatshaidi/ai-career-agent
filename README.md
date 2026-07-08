# AI Career Agent

AI Career Agent is a production-oriented repository for an AI-driven career automation platform. The repository now contains the project foundation, the PostgreSQL source-of-truth schema, the opportunity collection workflow, and the Block 4 AI Decision Engine that evaluates collected opportunities through OpenAI and persists the results in PostgreSQL.

## Project Goals

- Prepare a scalable repository foundation for further development blocks.
- Separate product logic, automation workflows, database assets, and operational scripts from day one.
- Keep the system maintainable, auditable, and safe for production growth.
- Preserve existing infrastructure and evolve the platform block by block without unsafe rewrites.
- Keep future LLM-provider replacement possible without changing scoring and persistence business logic.

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
|       |-- ai-decision-engine.md
|       |-- ai-decision-engine.output-schema.json
|       |-- collect-opportunities.md
|       `-- collect-opportunities.sources.json
|-- database/
|   |-- migrations/
|   `-- sql/
|-- docs/
|   |-- adr/
|   |-- runbooks/
|   |-- ai-decision-engine.md
|   |-- database.md
|   `-- opportunity-collection.md
|-- logs/
|-- n8n/
|   |-- exports/
|   `-- workflows/
|       |-- analyze-opportunities.json
|       `-- collect-opportunities.json
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

Block 4 extends this architecture with a provider-isolated AI Decision Engine:

- `user_intelligence_profiles` stores editable machine-readable user preferences
- `opportunity_analysis_jobs` stores durable queue and retry state
- `opportunity_ai_analysis` and `opportunity_scores` store per-profile AI outputs and score history
- PostgreSQL computes the final Opportunity Score and recommended action
- n8n only claims jobs, calls OpenAI, and returns structured JSON to PostgreSQL

This separation keeps scoring and persistence logic outside the provider-specific workflow branch and makes future LLM replacement much safer.

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

8. Import `n8n/workflows/collect-opportunities.json` and `n8n/workflows/analyze-opportunities.json` only after PostgreSQL migrations are applied and the required credentials exist in n8n.

## Development Process

- Block 1 builds the foundation only.
- Block 2 adds the V1 PostgreSQL schema, SQL migrations, and migration validation assets.
- Block 3 adds the opportunity collection workflow, source contracts, ingestion SQL helpers, and deduplicated persistence into PostgreSQL.
- Block 4 adds the AI Decision Engine, editable user intelligence profiles, and deterministic final scoring.
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

Telegram notifications, Google Sheets journaling, backend APIs, and UI remain intentionally out of scope for the current repository state.
