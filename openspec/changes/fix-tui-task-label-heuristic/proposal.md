---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - openspec/specs/review-sessions/spec.md
  - openspec/specs/run-controller/spec.md
  - openspec/CONSTITUTION.md
---

**Change Type**: implementation

# Fix TUI task label heuristic

## Problem / Context

`review-gauntlet run` TUI determines the current task label (e.g. `REVIEW PENDING CELLS`, `FIX CONFIRMED FINDING`) by **parsing the ready prompt body text** with keyword matching in `format_task_title` (`run_tui.py:612`). The matching logic scans the lowercased prompt for substrings like `("confirmed", "fix")`, `("pending", "review")`, `("stale", "review")` in priority order.

This is fragile and already produces incorrect results. A pending-review prompt contains the instruction "Record confirmed issues as findings" and "do not triage, fix, or mark other files", so both `confirmed` and `fix` appear in the text. Because `("confirmed", "fix")` is checked before `("pending", "review")`, a session that has **never been reviewed** displays `FIX CONFIRMED FINDING` in the TUI Activity panel and current-task display.

Root cause: the TUI infers task kind from natural-language prompt text instead of using the structured `next_required_action` signal that the CLI already computes deterministically in `_next_action` (`cli.py:2807`).

## Proposed Solution

Replace prompt-text parsing with structured-signal mapping.

### Core design

| Concern | Before | After |
|---------|--------|-------|
| Task title source | `format_task_title(prompt)` keyword scan | `format_task_title_from_action(next_required_action, coverage, findings)` |
| `step_started` event payload | `{step, prompt}` | `{step, prompt, next_required_action}` |
| `RunSnapshot` task display | parses `snapshot.next_ready_prompt` | reads `snapshot.next_required_action` + `snapshot.coverage` |
| Activity `step_started` detail | parses `event.payload["prompt"]` | reads `event.payload["next_required_action"]` |
| `ReadyPrompt` callable return | `str \| None` (prompt only) | `ReadyTask \| None` (prompt + next_required_action) |

### Action-to-title mapping

| `next_required_action` | Coverage / finding disambiguator | Title |
|---|---|---|
| `run_review` | `coverage.pending > 0` | `REVIEW PENDING CELLS` |
| `run_review` | `coverage.stale > 0` (no pending) | `REVIEW STALE CELLS` |
| `triage_findings` | — | `TRIAGE FINDINGS` |
| `fix_confirmed_findings` | — | `FIX CONFIRMED FINDING` |
| `run_verify_fixes` | — | `VERIFY FIXES` |
| `resolve_finalize_blockers` | — | `RESOLVE FINALIZE BLOCKERS` |
| `finalize` | — | `FINALIZE SESSION` |
| missing / unknown | — | `READY TASK` |

### Flow

1. `RunSnapshotReadinessProvider` builds one `_StatusContext` per readiness query
2. From that context, derives both the prompt text (existing `_ready_prompt_from_context`) and `next_required_action` (existing `_next_action`)
3. Returns `ReadyTask(prompt=..., next_required_action=...)` to `RunController`
4. `RunController.run()` emits `step_started` with `next_required_action` in payload
5. `RunController.snapshot()` already populates `RunSnapshot.next_required_action` from status — unchanged
6. `run_tui.dashboard_state` calls `format_task_title_from_action(snapshot.next_required_action, snapshot.coverage, snapshot.findings)` instead of `format_task_title(snapshot.next_ready_prompt)`
7. `run_tui._event_detail` for `step_started` reads `event.payload["next_required_action"]` instead of parsing prompt

## Acceptance Criteria

- A fresh `init` followed by `run` displays `REVIEW PENDING CELLS` in the Activity panel and current-task display, not `FIX CONFIRMED FINDING`
- `format_task_title` no longer scans prompt body text for keywords to determine task kind
- Task title is determined solely by `next_required_action` and, for `run_review`, the `pending` vs `stale` coverage counts
- `step_started` event payload includes `next_required_action`
- Activity `step_started` detail uses `event.payload["next_required_action"]`, not prompt text
- When `next_required_action` is missing or unknown, the TUI displays `READY TASK` without misclassifying
- `FIX CONFIRMED FINDING` appears only when `next_required_action == "fix_confirmed_findings"`

## Explicit Completion Conditions

1. `run_tui.py` contains no keyword-matching logic that scans `next_ready_prompt` text to decide task kind
2. `run_tui.py` `dashboard_state` constructs the task display from `snapshot.next_required_action` and `snapshot.coverage` / `snapshot.findings` counts
3. `run_tui.py` `_event_detail` for `step_started` reads `next_required_action` from the event payload
4. `run_controller.py` `RunController.run()` emits `step_started` with `next_required_action` in the payload
5. `run_controller.py` defines `ReadyTask` (or equivalent) carrying both `prompt` and `next_required_action`; `ReadyPrompt` callable type returns `ReadyTask | None`
6. `cli.py` `RunSnapshotReadinessProvider.ready_prompt` returns `ReadyTask` with `next_required_action` derived from the same `_StatusContext` that produced the prompt
7. A regression test proves that a pending-review prompt body containing `confirmed` and `fix` yields `REVIEW PENDING CELLS`, not `FIX CONFIRMED FINDING`
8. A test proves `step_started` event payload contains `next_required_action`
9. `make check` passes (format-check, lint, typecheck, test)

## Out of Scope

- `review-gauntlet ready` CLI command JSON output adding `next_required_action` (separate concern; the `ready` command still returns prompt text for external orchestrators)
- Changing `next_required_action` values or the `_next_action` priority order
- Changing the finalize-gate selection logic (already uses `next_required_action`)
- Redesigning the Activity panel layout
- Adding new `next_required_action` values
