# n8n

This directory is reserved for source-controlled n8n artifacts.

- `workflows/` is for maintained workflow definitions.
- `exports/` is for versioned exports or handoff snapshots when needed.

Current maintained workflow:

- `workflows/collect-opportunities.json`

Guidelines:

- Do not commit secrets or credential payloads.
- Prefer deterministic export naming.
- Treat n8n as orchestration and integration infrastructure, not as the owner of core business state.
- Keep source-specific fetch logic in workflow branches, but keep final deduplication and persistence in PostgreSQL.

A recommended workflow export naming pattern for later blocks is:

```text
YYYYMMDD-HHMM__workflow-name.json
```
