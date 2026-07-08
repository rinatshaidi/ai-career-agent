# ADR 0002 - Per-Profile AI Decision Engine

## Status

Accepted

## Context

Block 2 introduced placeholder tables for AI analysis and scoring, but those tables were still opportunity-centric.

Block 4 requires the system to decide whether a specific opportunity should be shown to a specific user. That means the decision cannot be modeled only at the opportunity level if the architecture is expected to scale beyond one user profile.

The system also needs:

- editable user intelligence preferences without code changes
- provider replaceability without rewriting business logic
- durable retry state for failed LLM calls
- deterministic final scoring that is not fully delegated to the model

## Decision

The architecture introduces:

- a dedicated `user_intelligence_profiles` entity
- a durable `opportunity_analysis_jobs` queue table
- per-profile linkage inside `opportunity_ai_analysis`
- per-profile linkage inside `opportunity_scores`
- PostgreSQL-owned score calculation and recommended-action thresholds

OpenAI remains the active LLM provider for Block 4, but the provider-specific concern is restricted to the workflow call that produces the structured decision payload.

## Consequences

Positive:

- user-specific decisions become first-class and scalable
- profile edits trigger reanalysis without code changes
- the score formula survives future LLM provider replacement
- retries and failures are auditable in PostgreSQL

Tradeoffs:

- schema complexity increases compared with the earlier placeholder design
- the workflow and SQL layers now coordinate through a stricter contract

This tradeoff is intentional because Block 4 is the first block where user-specific intelligence becomes a core business concern.
