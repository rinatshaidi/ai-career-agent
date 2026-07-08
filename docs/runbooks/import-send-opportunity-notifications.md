# Import Runbook - Send Opportunity Notifications

## Purpose

This runbook describes how to import the Block 5 delivery workflows into n8n without committing secrets.

## Files

- Main workflow: `n8n/workflows/send-opportunity-notifications.json`
- Callback template: `n8n/workflows/handle-opportunity-notification-actions.json`
- Contract: `config/n8n/telegram-delivery.md`

## Import Steps

1. Apply all PostgreSQL migrations through Block 5.
2. Import `n8n/workflows/send-opportunity-notifications.json`.
3. Keep `TELEGRAM_INLINE_ACTIONS_ENABLED=false` for the first activation unless you are also wiring the callback template.
4. Ensure the runtime can access `TELEGRAM_BOT_TOKEN`.
5. Run `delivery_upsert_telegram_target(...)` with the real user and real Telegram `chat_id`.
6. Manually execute the workflow to verify database access and Telegram API access.
7. Activate the workflow only after the manual run succeeds.

## Optional Callback Preparation

If you want the action buttons later:

1. Import `n8n/workflows/handle-opportunity-notification-actions.json`.
2. Expose its webhook endpoint to Telegram update delivery.
3. Keep the callback workflow inactive until the webhook route is correctly configured.
4. Only then set `TELEGRAM_INLINE_ACTIONS_ENABLED=true`.

## Required Environment Variables

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_API_BASE_URL`
- `TELEGRAM_BOT_NAME`
- `TELEGRAM_NOTIFICATION_PROFILE_SLUG`
- `TELEGRAM_NOTIFICATION_BATCH_SIZE`
- `TELEGRAM_NOTIFICATION_RETRY_DELAY_MINUTES`
- `TELEGRAM_NOTIFICATION_LOCK_TIMEOUT_MINUTES`
- `TELEGRAM_REQUEST_TIMEOUT_MS`
- `TELEGRAM_INLINE_ACTIONS_ENABLED`

## Failure Handling

On send failure:

- PostgreSQL moves the outbox row into `retry` or `failed`
- `system_logs` receives a structured event
- the same outbox row remains available for retry
