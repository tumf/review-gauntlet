---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
---

# Enforce status coverage priority over confirmed findings

**Change Type**: implementation

## Problem / Context

`review-gauntlet status` is the primary machine-readable signal for external orchestrators. A reported session showed `coverage.pending` and `coverage.stale` cells while `next_required_action` was `fix_confirmed_findings`. That ordering conflicts with the constitution's coverage-first principle and with the canonical review-session requirement that pending or stale review cells expose review work before finding work.

The current implementation already checks pending/stale cells before confirmed findings, but the regression surface is under-specified for the exact high-risk combination: pending/stale coverage plus a confirmed finding. The proposal makes this precedence explicit and verifies it with targeted tests so older or refactored status logic cannot silently prefer finding work while coverage remains incomplete.

## Proposed Solution

Strengthen the review-session behavior around `status.next_required_action` by adding explicit coverage-priority scenarios and regression tests for confirmed findings coexisting with pending and stale review cells. If implementation drift is found, update `src/review_gauntlet/cli.py` so `_next_action` always returns `run_review` whenever current coverage has pending or stale cells, regardless of confirmed, untriaged, reopened, or fixed-pending findings.

## Acceptance Criteria

- `review-gauntlet status --format json` returns `next_required_action: run_review` when at least one review cell is `pending`, even if one or more findings are `confirmed`.
- `review-gauntlet status --format json` returns `next_required_action: run_review` when at least one review cell is `stale`, even if one or more findings are `confirmed`.
- `finalize_blockers` still includes both coverage blockers and live finding blockers so no required work is hidden.
- `review-gauntlet ready --format json` remains aligned with status by prompting for review coverage before prompting for confirmed-finding fixes when pending or stale cells exist.
- Existing behavior for sessions with complete coverage and confirmed findings remains `next_required_action: fix_confirmed_findings`.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` contains deterministic next-action ordering that checks pending/stale review cells before finding states.
- Tests cover pending-plus-confirmed and stale-plus-confirmed status cases and assert `run_review`.
- Tests cover ready prompt precedence for pending/stale-plus-confirmed cases or reuse existing ready precedence helpers with confirmed findings.
- `make check` passes, including formatting, linting, type checking, and tests.

## Out of Scope

- Changing finding lifecycle semantics or terminal states.
- Auto-looping review coverage to completion.
- Modifying external orchestration behavior outside the CLI's status/ready signals.
- Changing dirty working tree or finalize blocker policies.
