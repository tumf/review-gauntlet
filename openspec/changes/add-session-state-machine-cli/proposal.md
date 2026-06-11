---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/models.py
  - src/review_gauntlet/planner.py
  - tests/test_cli.py
  - tests/test_planner.py
  - https://github.com/alibaba/open-code-review/tree/c323c6b40c72aa95d7cb801bedcb957b52ff9807
---

# Add session state machine CLI

**Change Type**: implementation

## Problem/Context

`review-gauntlet` currently generates inventories, review plans, and coverage matrices, but it does not persist review session state. The desired product shape is a CLI that advances a review session one explicit step at a time, rather than a tool that automatically loops until every review and finding is complete.

The current command surface (`inventory`, `plan`, `report`) is useful as a planning substrate, but it cannot represent repeated review runs, moving branch/worktree targets, finding triage, fixed-but-unverified findings, stale coverage, or finalization gates.

## Proposed Solution

Add a session-oriented CLI workflow:

- `review-gauntlet init`
- `review-gauntlet review`
- `review-gauntlet status`
- `review-gauntlet findings`
- `review-gauntlet mark`
- `review-gauntlet finalize`

The new workflow stores durable state under `.review-gauntlet/`, with an active session pointer and a ledger capable of tracking sessions, immutable review runs, review cells, findings, finding occurrences, and finding events.

`review-gauntlet review` advances the active session by one run only. It recalculates the current review universe, reconciles stale or new cells, updates coverage, deduplicates findings by stable fingerprint, verifies `fixed_pending_verification` findings when possible, and returns the next required human or external action. It must not automatically re-run itself, auto-fix code, auto-triage findings, or make risk decisions for the developer.

The review logic, prompts, and default rule corpus must be derived from Alibaba's `open-code-review` project at commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`. The implementation must port the built-in system rule map and rule documents, plus the review-output contract needed to normalize line-level comments into session findings. This adopts OCR's review rules and prompt corpus, but not its agent plugin behavior that can autonomously apply fixes.

## Acceptance Criteria

- A developer can initialize a review session for branch, worktree, or commit targets without starting an LLM review.
- A review session records its base/head policy, target mode, active session metadata, ruleset digest, review universe, and ledger state under `.review-gauntlet/`.
- The bundled review rules and prompts are traceable to the pinned `alibaba/open-code-review` snapshot and are included in the ruleset digest.
- `review-gauntlet review` performs exactly one review-run advancement and exits with a structured summary of coverage, findings, finalization readiness, and `next_required_action`.
- Repeated review runs in the same session deduplicate logically identical findings using stable session-level finding IDs rather than emitting duplicate new findings.
- `review-gauntlet mark` records human or external-LLM triage decisions without running review work.
- Marking a finding as fixed transitions it to `fixed_pending_verification`, not a terminal state.
- A later review run can move fixed findings to `fixed_verified` or `reopened` based on actual verification evidence.
- `review-gauntlet status` reports coverage state, finding state counts, finalization readiness, and the next required action.
- `review-gauntlet findings` lists open findings by default and can include terminal findings with `--all`.
- `review-gauntlet finalize` verifies completion conditions without running review work, and fails with actionable reasons when the session is incomplete.
- Existing `inventory`, `plan`, and `report` commands remain available and continue to pass their current JSON/markdown behavior tests.

## Explicit Completion Conditions

This change is complete when repository evidence shows all of the following:

- `src/review_gauntlet/cli.py` exposes the new session commands and keeps existing commands compatible.
- Session, run, review cell, finding, occurrence, and event models or persistence records exist in `src/review_gauntlet/` and are covered by typed tests.
- The review universe generation reuses or adapts existing inventory/planner behavior rather than duplicating unrelated classification logic.
- The repository contains the ported OCR system rule map, rule documents, and review comment normalization contract with attribution and tests proving rule selection parity for representative paths.
- Tests cover init/status/finalize flows, mark transitions, fixed verification behavior, finding deduplication, stale target handling, and incomplete-session failure reasons.
- `make check` passes.
- Manual CLI smoke commands demonstrate the typical session loop on a temporary repository without requiring credentials or external services.

## Out of Scope

- Automatically looping `review-gauntlet review` until completion.
- Automatically modifying source code to fix findings.
- Migrating OCR's autonomous agent plugin workflow that applies fixes after review.
- Automatically deciding false positive, waiver, or accepted-risk outcomes.
- Implementing CI/CD bot orchestration, notifications, PR workflow automation, or developer wait loops.
- Requiring live external LLM credentials for local verification; tests should use deterministic fakes, fixtures, or adapters.
