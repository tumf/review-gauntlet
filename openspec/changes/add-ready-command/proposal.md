---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli.py
  - openspec/specs/review-sessions/spec.md
  - openspec/CONSTITUTION.md
---

# Add Ready Command

**Change Type**: implementation

## Problem/Context

`review-gauntlet status` currently exposes `next_required_action`, but values such as `triage_findings` are too coarse to hand directly to an external coding agent. Users want an agent-friendly command that selects the next review session step and emits a short prompt suitable for an agent that already knows the review-gauntlet task execution skill.

The command must remain aligned with the project constitution: review-gauntlet provides explicit state and verdicts, orchestration remains external, and one review command advances once. The new surface should therefore not add claim state, queue management, hidden loops, or automatic source modifications.

## Proposed Solution

Add a read-only `review-gauntlet ready [root] --format text|json` command that returns only the next skill-directed prompt:

- JSON output shape is exactly `{ "prompt": string | null }`.
- Text output is the prompt body, or `no ready task` when no prompt is available.
- Every non-null prompt starts with `Use the review-gauntlet task execution skill.`
- Prompts stay intentionally short: they identify the next work category and stop condition, while detailed procedures remain in the external skill.
- The command chooses one prompt deterministically from active session state and does not modify the ledger, findings, review cells, git state, or checkpoint files.

The prompt selection order is:

1. Re-triage reopened findings.
2. Triage untriaged findings.
3. Fix the next confirmed finding.
4. Verify the next fixed-pending finding.
5. Review the next stale review cell.
6. Review the next pending review cell.
7. Finalize the session after intended git changes are committed.
8. Return no prompt when no ready work is available or only concrete blockers remain.

The finalize prompt must mention committing intended git changes before finalizing, but the command itself must not run git commit or finalize.

## Acceptance Criteria

- `review-gauntlet ready . --format json` returns a JSON object with exactly a `prompt` key whose value is a string or `null`.
- `review-gauntlet ready . --format text` prints only the selected prompt, or `no ready task` when no ready prompt exists.
- Every non-null ready prompt begins with `Use the review-gauntlet task execution skill.`
- Ready prompt selection is deterministic and follows the order: reopened, untriaged, confirmed, fixed-pending verification, stale review cell, pending review cell, finalize.
- The command is read-only: invoking it does not insert runs, update review cell state, update finding state, write finding events, write checkpoint files, or modify git state.
- `status` output remains unchanged; `ready` does not add `prompt` or additional task metadata to `status`.
- The finalize prompt includes the requirement to commit intended git changes before finalizing.
- Claim, release, queue, parallel execution, and task metadata management are not introduced.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` registers a top-level `ready` subcommand with the same root and `--format text|json` conventions as existing session commands.
- The `ready` implementation computes active session state from the existing ledger and returns only `{ "prompt": ... }` for JSON output.
- Unit or integration tests cover JSON/text output, prompt priority ordering, no-ready behavior, read-only behavior, unchanged `status` output, and finalize prompt wording.
- Existing CLI usage-error behavior remains consistent for missing roots or missing active sessions.
- `make check` passes.
- `cflx openspec validate add-ready-command --strict` passes.

## Out of Scope

- Implementing or updating the external review-gauntlet task execution skill.
- Adding claim, release, lease, timeout, queue, or parallel worker coordination features.
- Adding task IDs, task metadata, or structured completion contracts to `ready` output.
- Changing `status.next_required_action` semantics or adding prompt fields to `status`.
- Adding `review --cell` or changing review cell selection behavior.
- Automatically committing changes, finalizing sessions, marking findings, or running review work from `ready`.
