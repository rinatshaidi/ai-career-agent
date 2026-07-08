# Database

This directory stores PostgreSQL-related assets that belong in source control.

- `migrations/` stores ordered schema changes.
- `sql/` stores curated SQL assets such as verification queries, utility queries, or operational statements that are not migration files.

Block 2 introduces the initial V1 schema. Migration files follow an ordered timestamp-based naming convention:

```text
YYYYMMDDHHMMSS__short_description.sql
```

To validate migrations without touching production infrastructure:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

If Docker CLI is available locally, you can also validate against a disposable PostgreSQL container:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode docker
```

Block 3 adds ingestion helper functions and workflow support SQL. Verification SQL for collection helpers lives in `database/sql/verify_block3_collection.sql`.

Block 4 adds AI decision engine tables, per-profile analysis enhancements, and workflow support SQL. Verification SQL for the AI decision engine lives in `database/sql/verify_block4_decision_engine.sql`.
