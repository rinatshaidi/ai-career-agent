# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows semantic versioning once executable releases begin.

## [Unreleased]

### Added

- initial Block 1 repository foundation
- project documentation baseline with README, PRD, architecture document, and ADR
- production-oriented directory layout for apps, packages, docs, config, database, n8n, scripts, tests, and logs
- root environment template and git hygiene rules
- safe Docker Compose baseline with opt-in local infrastructure profile
- PowerShell validation script for repository structure
- V1 PostgreSQL schema migrations for users, profiles, sources, opportunities, analysis, scores, notifications, journal, and operational logs
- disposable migration validation script and schema verification SQL
- dedicated database design documentation for Block 2
- Block 3 collection helper functions for source registration, opportunity upsert, and batch ingestion logging
- `Collect Opportunities` workflow with RSS and HeadHunter connector branches
- source catalog contract and workflow validation script
- Block 4 `user_intelligence_profiles` and `opportunity_analysis_jobs` schema for editable AI preferences and durable decision queueing
- Block 4 SQL helper functions for AI profile upsert, queue claiming, score calculation, analysis persistence, and failure handling
- `Analyze Opportunities` workflow with OpenAI structured JSON analysis and PostgreSQL-backed retry handling
- Block 4 documentation, ADR, runbooks, and workflow validation script
