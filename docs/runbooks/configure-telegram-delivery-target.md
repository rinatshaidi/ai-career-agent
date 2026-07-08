# Runbook - Configure Telegram Delivery Target

## Purpose

Block 5 requires a real Telegram `chat_id` in PostgreSQL.

The delivery target is stored in:

- `user_profiles.profile_data.telegram_delivery`

Managed helper:

- `delivery_upsert_telegram_target(...)`

## Recommended Process

1. Ensure the target `users.id` already exists.
2. Obtain the real Telegram `chat_id` for the user or channel.
3. Execute the helper function in PostgreSQL.
4. Keep `enabled = true` only for destinations that should actually receive notifications.

## Execution Pattern

```sql
SELECT *
FROM delivery_upsert_telegram_target(
    p_user_id := '<real-user-uuid>'::uuid,
    p_chat_id := '<real-telegram-chat-id>',
    p_delivery_enabled := true,
    p_bot_name := 'Ri assistant'
);
```

Replace every placeholder with the real values before execution.

## Notes

- Do not use placeholder or fake `chat_id` values in the live database.
- The delivery workflow will skip users without a configured Telegram target.
- The bot token itself is not stored in PostgreSQL and must remain in runtime secrets.
