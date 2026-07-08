# Collect Opportunities Configuration

This file documents the configuration contract for the Block 3 `Collect Opportunities` workflow.

## Implemented Source Types

- RSS feeds
- HeadHunter official vacancies API

## Official-Only Telegram Position

Telegram channel collection is intentionally limited to the official Bot API model. The workflow repository includes the architecture contract, but does not activate a generic Telegram channel collector because the official Bot API does not provide a production-safe general read API for arbitrary public channels.

If Telegram collection is enabled in a future environment, it must use:

- a bot owned or controlled by the project
- channels where the bot is explicitly added for updates
- official `channel_post` / `edited_channel_post` delivery patterns only

## Environment Variables

- `COLLECT_RSS_WWR_URL`
- `COLLECT_RSS_REMOTEOK_URL`
- `COLLECT_HH_AUTOMATION_URL`
- `COLLECT_HH_OPENAI_URL`
- `COLLECT_TELEGRAM_ENABLED`

If these are not supplied, the workflow uses the real default URLs stored in the workflow expressions and in `collect-opportunities.sources.json`.

## Config Reference Strategy

Every source inserted into PostgreSQL uses a `config_reference` that points back to this repository contract. That gives the source catalog a stable trace to the source definition without storing secrets in SQL.
