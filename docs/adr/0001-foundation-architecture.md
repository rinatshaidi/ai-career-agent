# ADR 0001 - Foundation Architecture

- Status: Accepted
- Date: 2026-07-08

## Context

The project needs a production-ready repository foundation before any business logic, workflow implementation, database schema work, or external-channel behavior is added.

The foundation must support future scaling while keeping the current block narrow and safe.

## Decision

The project adopts a modular monorepo foundation with dedicated areas for:

- future executable services in `apps/`
- shared contracts in `packages/shared/`
- database assets in `database/`
- automation artifacts in `n8n/`
- operational and architectural documentation in `docs/`
- environment and runtime configuration in `config/`

The future primary implementation runtime is planned as Node.js LTS with TypeScript, while n8n remains the automation and integration runtime and PostgreSQL remains the intended source of truth.

## Rationale

- It preserves a single repository for coordinated delivery.
- It avoids the operational cost of a premature multi-repo split.
- It makes boundaries explicit before feature code appears.
- It gives a clean path toward CI/CD, migrations, runbooks, tests, and deployment automation.
- It prevents n8n workflows from becoming the accidental owner of core business state.

## Consequences

- The repository is ready for later blocks without structural rework.
- Business logic remains intentionally absent in Block 1.
- Future teams can add services incrementally without flattening the architecture.
