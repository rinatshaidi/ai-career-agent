# Changelog

## 1.0.0 - Production V1

- expanded collection with Remotive, Jobicy, Работа России, and independent Greenhouse boards
- added cross-source URL and content deduplication with provenance tracking
- replaced fixed career directions with user-created multi-direction Telegram profiles
- added semantic per-direction AI assessment with `priority`, `review`, and `archive` decisions
- redesigned Telegram cards around match evidence, risks, actions, salary, work format, and response draft
- added persistent source schedules, queue limits, recovery behavior, and provider isolation
- added OpenAI input/output token accounting and an aggregate production audit
- added SQLite backup automation with integrity checking and short retention
- increased automated coverage from 76 to 140 tests

## 0.3.0 - Python Production Rewrite

- replaced the n8n runtime with a standalone Python application
- added Habr Career, Remote OK, and We Work Remotely providers
- added typed normalization and persistent SQLite deduplication
- added structured OpenAI analysis and score-based Telegram delivery
- added Telegram candidate-profile onboarding
- added independent provider schedules and persistent source-run statistics
- added Docker health checks, retries, rotating logs, and recovery behavior
- added 76 automated tests

## 0.1.0 - n8n Prototype

- established the original AI Career Agent product concept
- implemented opportunity collection, analysis, delivery, and feedback workflows
- created the initial PostgreSQL data model and operational documentation
