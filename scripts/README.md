# Scripts

This directory stores operational and development automation scripts.

Script principles:

- scripts must be safe to run repeatedly whenever practical
- scripts must be explicit about environment assumptions
- scripts must not hide destructive behavior
- validation and maintenance automation should live here instead of inside ad hoc terminal history

Available scripts:

- `validate-foundation.ps1` verifies that the expected repository structure and required files exist.
- `validate-migrations.ps1` validates SQL migration presence and can optionally apply migrations against a disposable PostgreSQL container.
- `validate-collection-workflow.ps1` verifies that the `Collect Opportunities` workflow and source contract files are present and structurally valid.
- `validate-ai-decision-workflow.ps1` verifies that the `Analyze Opportunities` workflow and decision output contract files are present and structurally valid.
- `validate-telegram-delivery-workflow.ps1` verifies that the Telegram delivery workflow and callback workflow files are present and structurally valid.
- `validate-feedback-learning-workflow.ps1` verifies the Block 6 callback workflow, retention workflow, and Google Sheets archive contract files.

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-foundation.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-collection-workflow.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-ai-decision-workflow.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-telegram-delivery-workflow.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-feedback-learning-workflow.ps1
```
