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
- appending a lightweight entry to the Google Sheets journal contract table

## Maintained Workflows

- `n8n/workflows/send-opportunity-notifications.json`

Prepared callback template:

- `n8n/workflows/handle-opportunity-notification-actions.json`

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
    "bot_name": "Ri assistant"
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

Optional action buttons are prepared behind `TELEGRAM_INLINE_ACTIONS_ENABLED=true`:

- `Сохранить`
- `Не интересно`
- `Позже`

The callback workflow template is committed, but full feedback automation is intentionally deferred to the next block.

## Google Sheets Journal

Block 5 does not treat Google Sheets as a primary datastore.

On successful Telegram delivery, PostgreSQL appends a lightweight row to `google_sheets_journal` with:

- `date`
- `source`
- `opportunity_type`
- `title`
- `score`
- `status`
- `url`

This keeps the journal contract up to date without introducing a direct Google Sheets dependency in the workflow.
