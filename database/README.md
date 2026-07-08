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

Block 5 adds Telegram delivery outbox helpers, callback-action capture support, and journal-contract support SQL. Verification SQL for the delivery engine lives in `database/sql/verify_block5_telegram_delivery.sql`.

Block 6 adds feedback history tables, a separate learning dataset, Google Sheets archive-sync support, and 60-day working-memory retention SQL. Verification SQL for the feedback engine lives in `database/sql/verify_block6_feedback_learning.sql`.

Block 6.5 adds a production-integration corrective migration that updates the Telegram bot fallback from `Ri assistant` to `Ri Career Agent` in the effective delivery helper functions and includes `database/sql/verify_block65_production_integration.sql` to assert the final runtime definitions.
