# Telegram Delivery Workflow Contract

## Purpose

This contract describes the production-ready interface between PostgreSQL and n8n for Block 5.

The Telegram delivery layer does not decide whether an opportunity should be shown.

That decision already belongs to PostgreSQL through:

- `opportunity_ai_analysis`
- `opportunity_scores`
- `recommended_action`
- `is_current`

The delivery workflow is responsible only for:

- syncing eligible current AI analyses into the `notifications` outbox
- claiming unsent Telegram notifications
- formatting a compact Telegram message
- sending the message through the configured bot token
- marking the outbox row as sent or failed
- exposing supported feedback actions through inline buttons

## Maintained Workflows

- `n8n/workflows/handle-opportunity-notification-actions.json`
- `n8n/workflows/send-opportunity-notifications.json`

## PostgreSQL Contracts

### Outbox

The outbox owner is the `notifications` table.

Block 5 uses:

- `channel = 'telegram'`
- `notification_type = 'opportunity_match'`

Allowed delivery statuses:

- `pending`
- `in_progress`
- `retry`
- `sent`
- `failed`
- `cancelled`

### Delivery Functions

- `delivery_upsert_telegram_target(...)`
- `delivery_sync_telegram_outbox(...)`
- `delivery_claim_notification_batch(...)`
- `delivery_mark_notification_sent(...)`
- `delivery_mark_notification_failed(...)`
- `delivery_record_notification_action(...)`

## Telegram Target Contract

The delivery target is stored in `user_profiles.profile_data` under:

```json
{
  "telegram_delivery": {
    "chat_id": "<real-chat-id>",
    "enabled": true,
    "bot_name": "Ri Career Agent"
  }
}
```

This contract is managed through:

- `delivery_upsert_telegram_target(...)`

## Environment Variables

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_API_BASE_URL`
- `TELEGRAM_BOT_NAME`
- `TELEGRAM_NOTIFICATION_PROFILE_SLUG`
- `TELEGRAM_NOTIFICATION_BATCH_SIZE`
- `TELEGRAM_NOTIFICATION_RETRY_DELAY_MINUTES`
- `TELEGRAM_NOTIFICATION_LOCK_TIMEOUT_MINUTES`
- `TELEGRAM_REQUEST_TIMEOUT_MS`
- `TELEGRAM_INLINE_ACTIONS_ENABLED`

## Delivery Rules

Only current AI analyses with these actions are eligible:

- `apply_now`
- `review_manually`
- `watchlist`

The workflow must not send:

- `skip`
- rows without current AI analysis
- already-sent opportunities
- cancelled notifications

Idempotency is enforced in PostgreSQL through a unique Telegram outbox index for `(user_id, opportunity_id, user_intelligence_profile_id, channel, notification_type)`.

## Inline Actions

The always-safe inline button is:

- `Открыть`

Supported action buttons behind `TELEGRAM_INLINE_ACTIONS_ENABLED=true`:

- `Откликнулся`
- `Сохранить`
- `Позже`
- `Не интересно`
- `Уже выполнено`
- `Получил проект`
- `Получил работу`
- `Отказ`
- `Нет ответа`

The callback workflow is maintained as part of Block 6 and hands feedback ownership to PostgreSQL plus the Google Sheets archive contract.

## Google Sheets Journal

Telegram delivery does not write archive rows on send.

The archive is updated later by the feedback workflow and only for:

- `apply_now`
- `review_manually`

This keeps delivery transport separate from the long-lived archive lifecycle.
