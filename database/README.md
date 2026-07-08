# Database

This directory is the future home of all PostgreSQL-related assets that belong in source control.

- `migrations/` is reserved for ordered schema changes.
- `sql/` is reserved for curated SQL assets such as utility queries, database maintenance scripts, and verified operational statements.

Block 1 intentionally does not define a schema. When migrations begin in later blocks, use an ordered naming convention such as:

```text
YYYYMMDDHHMMSS__short_description.sql
```
