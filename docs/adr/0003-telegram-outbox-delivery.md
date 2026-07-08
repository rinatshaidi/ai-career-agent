# ADR 0003 - PostgreSQL-Owned Telegram Outbox Delivery

## Status

Accepted

## Context

Block 5 needs reliable Telegram delivery without letting Telegram or n8n decide opportunity relevance.

The system also needs:

- idempotent delivery
- retryable failures
- no duplicate sends for the same opportunity
- a clear boundary between AI decisioning and user-facing delivery

## Decision

The architecture keeps Telegram delivery state in PostgreSQL by extending the existing `notifications` table into a real outbox.

The workflow only:

- syncs eligible current analyses into the outbox
- claims outbox rows
- sends Telegram messages
- reports success or failure back to PostgreSQL

Delivery routing is stored in `user_profiles.profile_data.telegram_delivery` rather than introducing a new delivery-target table in this block.

## Consequences

Positive:

- delivery is idempotent at the database level
- retries survive workflow restarts
- Telegram remains a transport, not a decision engine
- journal rows can be appended without introducing Google Sheets coupling

Tradeoffs:

- `notifications` now carries more operational fields
- delivery-target metadata remains JSONB-based in `user_profiles` for this block

This tradeoff is intentional because it preserves the current repository architecture while delivering a production-ready outbox pattern.
