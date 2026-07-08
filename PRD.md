# PRD - AI Career Agent

## Product Summary

AI Career Agent is a production-grade automation system that collects real career opportunities, evaluates them with AI, delivers only relevant matches to Telegram, captures user feedback, and preserves a durable dataset for future learning.

The system is intentionally delivered block by block so the architecture, persistence, and automation layers remain stable as business capability grows.

## Problem Statement

Career and project discovery workflows often fragment across:

- Telegram chats
- spreadsheets
- browser tabs
- notes
- manual reminders
- disconnected automations

This fragmentation makes it hard to:

- keep one trusted source of truth
- avoid duplicate opportunities
- understand which recommendations are actually useful
- build a future training dataset from real user outcomes

## Product Objectives

- Collect real opportunities from approved sources into one canonical PostgreSQL model.
- Evaluate opportunities against editable user intelligence profiles.
- Deliver only relevant opportunities to Telegram.
- Capture real user actions in a structured, idempotent way.
- Maintain Google Sheets as a long-lived archive without turning it into the operational database.
- Build a durable learning dataset without retraining the AI yet.

## Current Implemented Scope

### Block 1

- repository foundation
- documentation baseline
- Docker Compose baseline
- development and validation structure

### Block 2

- V1 PostgreSQL schema
- indexes, triggers, and verification SQL

### Block 3

- opportunity collection from supported official sources
- normalization to one canonical Opportunity model
- deduplicated PostgreSQL persistence

### Block 4

- editable `user_intelligence_profiles`
- OpenAI-backed AI Decision Engine
- deterministic PostgreSQL-owned score persistence

### Block 5

- PostgreSQL-owned Telegram outbox
- retry-safe opportunity delivery workflow
- Telegram inline action transport

### Block 6

- idempotent Telegram feedback capture
- feedback history in PostgreSQL
- separate learning dataset in PostgreSQL
- Google Sheets archive updates keyed by `archive_key`
- automatic 60-day cleanup of transient working memory

## Block 6 Scope

Block 6 includes:

- capturing supported user actions from Telegram
- updating `notifications`
- updating coarse `opportunities.status`
- writing durable feedback history
- writing a separate future-training dataset
- upserting Google Sheets archive rows only for `apply_now` and `review_manually`
- preserving long-lived evidence while deleting transient working memory after 60 days

## Explicitly Out Of Scope

The following remain outside the current repository state:

- automatic AI retraining
- changing the current Opportunity Score algorithm
- backend API
- Web UI
- dashboards
- new source connectors beyond the already accepted blocks

## Supported User Actions

The current feedback engine supports:

- `applied`
- `saved`
- `later`
- `not_interested`
- `already_done`
- `got_project`
- `got_job`
- `rejected`
- `no_response`

## Non-Functional Requirements

- PostgreSQL remains the source of truth for operational state.
- Google Sheets remains an archive, not the working database.
- All user actions must be idempotent.
- The architecture must support multiple users.
- Long-lived learning evidence must survive working-memory cleanup.
- Secrets must stay outside committed source code and workflow exports.
- Every block must remain production-ready without mock data or temporary logic.

## Success Criteria For The Current Repository State

- Opportunities can be collected, analyzed, delivered, and annotated by real user actions.
- Telegram feedback updates PostgreSQL and the Google Sheets archive without duplicate rows.
- `user_feedback_history` preserves append-only user interaction history.
- `learning_feedback_dataset` preserves future-training evidence separately from `opportunities`.
- Working-memory tables can be purged after 60 days without losing feedback or learning history.

## Key Delivery Artifacts

- `README.md`
- `PRD.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `docs/database.md`
- `docs/ai-decision-engine.md`
- `docs/telegram-delivery-engine.md`
- `docs/feedback-learning-engine.md`
- `n8n/workflows/*.json`
- `database/migrations/*.sql`
- `scripts/validate-*.ps1`
