# PRD - AI Career Agent

## Product Summary

AI Career Agent is intended to become a production-grade system for automating and augmenting career management workflows with AI, workflow orchestration, and structured data handling.

Block 1 does not implement product features. It creates the technical foundation required to build them safely in later blocks.

## Problem Statement

Career-related workflows often become fragmented across chat tools, spreadsheets, notes, manual reminders, and disconnected automations. This creates poor traceability, low reuse, and limited scalability once the workflow grows beyond a personal setup.

The project needs a foundation that can support reliable automation, structured persistence, controlled integrations, and future AI-assisted workflows without early architectural debt.

## Product Objectives

- Centralize future career-agent capabilities in a maintainable repository.
- Enable controlled collaboration between application code, automation workflows, and data assets.
- Provide a path toward production operations, observability, and secure configuration handling.
- Support future incremental delivery by development blocks.

## Block 1 Scope

Block 1 includes:

- repository inspection and initialization in the required local path
- documentation baseline
- architecture definition
- directory layout
- environment template
- git hygiene rules
- Docker Compose baseline
- structure for documentation, configuration, database assets, SQL migrations, n8n workflows, scripts, tests, and logs

## Out Of Scope For Block 1

The following are explicitly excluded from implementation in Block 1:

- opportunity discovery
- AI analysis logic
- Telegram bot implementation
- PostgreSQL schema implementation
- n8n workflow implementation
- Opportunity Score logic

These items belong to subsequent blocks and are not implemented in this repository state.

## Non-Functional Requirements

- Production-oriented repository structure
- Clear separation of concerns
- Secure secret handling through environment variables and external credential stores
- Low operational ambiguity between code, workflow, and data ownership
- Traceable changes through changelog and ADRs
- Readiness for CI/CD, observability, and multi-environment expansion in future blocks

## Success Criteria For Block 1

- The repository exists in `C:\codex\ai-career-agent`.
- Git is connected to the existing GitHub repository.
- The repository contains a coherent production-ready foundation.
- Documentation explains purpose, structure, architecture, and next development steps.
- The project can proceed to Block 2 without repository rework.

## Key Delivery Artifacts

- `README.md`
- `PRD.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- supporting directory structure and guidance files

## Acceptance Boundary

If a requirement would introduce business logic, real workflow implementation, database schema design, or integration behavior, it is outside Block 1 and must remain unimplemented at this stage.
