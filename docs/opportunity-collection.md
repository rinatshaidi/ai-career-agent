# Opportunity Collection System - Block 3

## Scope

Block 3 introduces the production-oriented collection layer for AI Career Agent.

The system is responsible for:

- collecting real data from approved sources
- normalizing every source into the unified Opportunity model
- deduplicating records automatically
- saving results to PostgreSQL
- logging source-level failures without stopping the other source branches

Block 3 does not implement:

- AI analysis
- opportunity scoring
- Telegram notifications
- Google Sheets
- backend APIs
- web interface
- worker services

## Implemented Sources

### RSS Feeds

Implemented through the main workflow with generic RSS normalization.

Current real feed configuration:

- We Work Remotely RSS
- Remote OK RSS

These are consumed as RSS sources, not as dedicated site-specific custom scrapers.

### HeadHunter

Implemented through the official HeadHunter vacancies API.

Current search profiles:

- automation / workflow / integration / n8n
- OpenAI / LLM / AI automation / Telegram bot

### Telegram Channels

Not activated as a production-ready collector in Block 3.

Reason:

- the official Telegram Bot API works through updates delivered to the bot
- this is suitable only for channels where the bot is intentionally present and managed
- it is not a safe official mechanism for arbitrary public-channel historical collection

The repository includes the official-only architecture contract for a future controlled implementation, but does not ship an unofficial scraper.

## Main Workflow

Workflow file:

- `n8n/workflows/collect-opportunities.json`

Workflow name:

- `Collect Opportunities`

Connector branches:

- RSS | We Work Remotely
- RSS | Remote OK
- HeadHunter | Automation
- HeadHunter | OpenAI

Each branch follows the same pattern:

1. ensure the source exists in PostgreSQL
2. fetch source data from the real endpoint
3. normalize source items into Opportunity-shaped payloads
4. ingest the batch through PostgreSQL helper functions
5. write source-level run logs

## Opportunity Normalization

Every source is mapped to the same Opportunity model fields:

- `source_id`
- `external_id`
- `title`
- `description`
- `raw_text`
- `url`
- `company_name`
- `opportunity_type`
- `source_type`
- `location`
- `remote_type`
- `budget_min`
- `budget_max`
- `currency`
- `published_at`
- `collected_at`
- `status`

The workflow prepares a `dedupe_key` for each normalized item. PostgreSQL converts that key into the stored `duplicate_hash`.

## Deduplication Strategy

Deduplication is implemented in PostgreSQL, not in n8n.

The collection helper uses:

- source-level uniqueness through `(source_id, external_id)` when the source provides a stable external identifier
- cross-source deduplication through a SHA-256 `duplicate_hash` derived from the normalized `dedupe_key`

This means every connector uses the same deduplication path and the workflow does not maintain source-specific duplicate logic.

## Error Handling

The workflow is branch-based. Each connector writes its own run result through `collection_ingest_source_batch(...)`.

If a source fetch fails:

- the branch records a failed or partial `source_run_logs` entry
- a structured `system_logs` event is written
- other source branches continue independently

## Database Support Added In Block 3

New helper functions:

- `collection_ensure_source(...)`
- `collection_upsert_opportunity(...)`
- `collection_ingest_source_batch(...)`

These functions centralize source upsert, opportunity deduplication, batch persistence, and run logging.

## Future Source Extension Pattern

Future sources should follow the same connector contract:

1. fetch raw data from an official source
2. normalize into the shared Opportunity payload shape
3. pass the normalized batch into `collection_ingest_source_batch(...)`

This pattern is already suitable for:

- Habr Career
- Wellfound
- company career pages
- marketplaces that later expose an official API or official feed

## Validation

Repository-level validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-foundation.ps1
```

Migration-level validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

Workflow/config validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-collection-workflow.ps1
```
