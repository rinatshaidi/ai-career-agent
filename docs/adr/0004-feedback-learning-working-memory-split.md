# ADR 0004 - Separate Working Memory From Learning History

## Status

Accepted in Block 6.

## Context

The project needs to keep:

- short-lived operational state for collection, AI analysis, and delivery
- durable feedback evidence for future analytics and model training
- a Google Sheets archive without duplicate rows

Keeping all of this inside `opportunities` or inside `notifications.payload` would make retention, analytics, and future training much harder.

## Decision

The architecture separates these concerns:

- `opportunities`, `opportunity_ai_analysis`, `opportunity_scores`, `notifications`, `source_run_logs`, and `system_logs` remain working memory
- `user_feedback_history` becomes the append-only user interaction history
- `learning_feedback_dataset` becomes the future AI-training dataset
- `google_sheets_journal` becomes the durable Google Sheets archive-sync contract with `archive_key`

The feedback workflow updates coarse working-memory state, but the exact user outcome lives in the durable feedback tables.

## Consequences

Positive:

- working memory can be purged after 60 days without losing learning evidence
- Google Sheets updates stay idempotent through a stable archive key
- the learning dataset is queryable without joining to expired opportunities
- future analytics and retraining pipelines can start from already-curated data

Tradeoff:

- the schema gains more tables and functions
- the callback workflow becomes more important operationally

This tradeoff is acceptable because it avoids mixing transient runtime state with long-lived product intelligence.
