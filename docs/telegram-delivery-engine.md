# Telegram Delivery Engine - Block 5

## Scope

Block 5 introduces the production-ready Telegram delivery layer for AI Career Agent.

The system is responsible for:

- reading only current AI-approved opportunities from PostgreSQL
- materializing durable Telegram outbox records in `notifications`
- delivering messages to Telegram
- updating delivery status after success or failure
- keeping retry state in PostgreSQL
- appending a lightweight Google Sheets journal contract row after successful delivery

Block 5 does not implement:

- feedback learning
- re-scoring
- new opportunity sources
- backend API
- web interface

## Main Principle

Telegram does not decide whether an opportunity should be shown.

That decision is already made in PostgreSQL through:

- `opportunity_ai_analysis`
- `recommended_action`
- `opportunity_scores`
- `is_current`

Telegram only delivers the result of the AI Decision Engine.

## Outbox Model

The existing `notifications` table is now the delivery outbox.

For Block 5:

- `channel = 'telegram'`
- `notification_type = 'opportunity_match'`

Additional delivery fields support:

- retry attempts
- lock ownership
- next retry time
- per-profile linkage

Idempotency is enforced with a unique Telegram outbox index per:

- user
- opportunity
- user intelligence profile
- channel
- notification type

This prevents the same opportunity from being queued repeatedly for the same user profile.

## Delivery Flow

Maintained workflow:

- `n8n/workflows/send-opportunity-notifications.json`

Workflow name:

- `Send Opportunity Notifications`

Execution pattern:

1. sync eligible current AI results into the Telegram outbox
2. claim a batch of unsent notifications
3. format a concise Telegram message
4. send the message through Telegram Bot API
5. mark the notification as `sent` or `retry` / `failed`
6. write a lightweight journal row into `google_sheets_journal` after successful delivery

## Eligibility Rules

The outbox accepts only current AI analyses where:

- `recommended_action` is `apply_now`, `review_manually`, or `watchlist`
- the AI analysis is `is_current = true`
- the opportunity is still in `analyzed` status
- the user has a configured Telegram target

The delivery engine does not send:

- `skip`
- opportunities without current AI analysis
- already-created Telegram notifications for the same user/profile/opportunity
- cancelled notifications

## Telegram Target Storage

Telegram destination settings are stored in `user_profiles.profile_data.telegram_delivery`.

Managed helper:

- `delivery_upsert_telegram_target(...)`

Stored fields:

- `chat_id`
- `enabled`
- `bot_name`

This keeps delivery routing editable in PostgreSQL without code changes.

## Error Handling

If Telegram delivery fails:

- the notification becomes `retry` or `failed`
- the error is written to `system_logs`
- the opportunity is not lost
- retry remains possible through the same outbox row

Stale `in_progress` locks are re-queued by the claim function after the configured timeout.

## Inline Actions

Block 5 prepares inline actions without implementing the full feedback engine.

Always-safe button:

- `Открыть`

Optional buttons behind `TELEGRAM_INLINE_ACTIONS_ENABLED=true`:

- `Сохранить`
- `Не интересно`
- `Позже`

Prepared callback workflow template:

- `n8n/workflows/handle-opportunity-notification-actions.json`

This template only records the raw action into notification payload and logs it. It does not yet change scoring, ranking, or future AI behavior.

## Google Sheets Journal

Block 5 writes a lightweight row into `google_sheets_journal` on successful Telegram delivery.

Stored fields:

- `date`
- `source`
- `opportunity_type`
- `title`
- `score`
- `status`
- `url`

No direct Google Sheets API delivery is introduced in this block. The table remains the journal contract and future export source.

## Validation

Repository-level validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-foundation.ps1
```

Migration-level validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-migrations.ps1 -Mode static
```

Workflow validation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-telegram-delivery-workflow.ps1
```
