# Design: Repair Session Ledger and Triage Validation

## Scope

This change focuses on durable-state correctness and triage metadata safety. It does not add new user-facing workflow commands.

## Decisions

- Treat zero-row ledger updates as programmer or state errors, not no-ops.
- Keep finding IDs human-readable and session-scoped while making allocation monotonic across gaps.
- Validate user-provided date metadata before persistence, but tolerate corrupt existing metadata because users may already have local ledgers.
- Treat malformed terminal-decision metadata as blocking rather than ignored, preserving the constitution's requirement that unknown state remains visible.
- Avoid creating review-run evidence when no cell was actually evaluated.

## Verification Strategy

Use unit tests for store-level invariants and CLI integration tests for session/finalize behavior because correctness depends on the interaction between runs, findings, events, and status summaries.
