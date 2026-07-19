# Project Evolution

## Version 0.1: n8n Prototype

The first implementation validated the product concept with n8n workflows,
PostgreSQL functions, Telegram delivery, and feedback-oriented data flows.
It established the core idea: search for earning opportunities by task meaning
rather than job title alone.

The prototype is preserved under the `v0.1-n8n-prototype` tag.

## Version 0.3: Python Rewrite

The current implementation replaces workflow-specific runtime behavior with a
testable Python application.

| Area | n8n prototype | Python rewrite |
| --- | --- | --- |
| Orchestration | Multiple imported workflows | One typed application pipeline |
| Providers | Workflow branches | Independent provider classes |
| Normalization | Node-specific transformations | Shared `Opportunity` model |
| Storage | PostgreSQL functions | Self-contained SQLite repository |
| AI analysis | Workflow prompt nodes | Structured service with local validation |
| Telegram | Workflow delivery | Retry-safe client and notification history |
| Scheduling | Workflow schedules | Persistent per-provider intervals |
| Reliability | Workflow execution state | Recovery, retries, heartbeats, and health checks |
| Verification | Manual workflow checks | 76 automated tests |
| Deployment | Existing n8n infrastructure | Standalone Docker services |

## Why the Rewrite Was Made

The Python architecture provides clearer ownership boundaries, easier automated
testing, portable deployment, and predictable recovery after restarts. A new
source can be added without changing AI analysis, storage, or Telegram delivery.

The change is a product evolution rather than a separate unrelated project. Git
history records both stages, while the default branch contains only the current
maintained implementation.
