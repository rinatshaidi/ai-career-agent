# Scripts

This directory stores operational and development automation scripts.

Script principles:

- scripts must be safe to run repeatedly whenever practical
- scripts must be explicit about environment assumptions
- scripts must not hide destructive behavior
- validation and maintenance automation should live here instead of inside ad hoc terminal history

Block 1 includes a structure validation script to verify the repository foundation.

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-foundation.ps1
```
