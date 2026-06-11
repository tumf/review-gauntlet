---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/targets.py
  - src/review_gauntlet/inventory.py
---

# Add OCR-compatible init diff targets and full-repository review

**Change Type**: implementation

## Problem / Context

`review-gauntlet` currently keeps target selection on `init` and review execution on `review`, which matches the project constitution's one-step review command model. However, the current `init --worktree` behavior is not clearly aligned with OCR's diff-only review modes, and there is no explicit command surface for a full-repository review mode that goes beyond OCR.

Developers need a clear target model:

- OCR-compatible workspace diff review for staged, unstaged, and untracked changes.
- OCR-compatible branch range review for changed files between two refs.
- OCR-compatible single-commit review for files changed by one commit.
- review-gauntlet-only full repository review for every eligible project file.

## Proposed Solution

Keep range and scope selection on `review-gauntlet init` only. Do not add `--from`, `--to`, `--commit`, `--worktree`, or `--all` to `review-gauntlet review`.

Update `init` target handling so:

- `review-gauntlet init` defaults to OCR-compatible workspace diff mode.
- `review-gauntlet init --worktree` remains accepted as an explicit alias for workspace diff mode.
- `review-gauntlet init --from <base> --to <head>` builds the review universe from files changed between the refs.
- `review-gauntlet init --commit <oid>` builds the review universe from files changed by that commit.
- `review-gauntlet init --all` creates a full-repository review universe using the existing project inventory exclusions.

Document the OCR correspondence and the review-gauntlet-only `--all` mode in user-facing docs.

## Acceptance Criteria

- Running `review-gauntlet init` without target flags creates a workspace diff-targeted session and does not require `--worktree`.
- Running `review-gauntlet init --worktree` remains valid and equivalent to the default workspace diff target.
- Workspace diff sessions include staged files, unstaged files, and untracked non-ignored files, but not unrelated unchanged tracked files.
- Branch range sessions include eligible files changed between `--from` and `--to`, but not unrelated unchanged tracked files.
- Commit sessions include eligible files changed by the selected commit, and still record fixed head semantics.
- Full repository sessions are requested with `review-gauntlet init --all` and include all eligible project files returned by existing inventory rules.
- `review-gauntlet review` continues to advance only the active session once and does not accept target selection flags.
- README or equivalent project docs explain the mapping from OCR commands to `review-gauntlet init` plus `review`, and explain `--all` as an additional full-review mode not provided by OCR.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` exposes `init --all` and accepts no-flag `init` as workspace diff mode while leaving `review` target-option-free.
- Target resolution and review-universe construction separate diff-based file discovery from full-inventory discovery in source code.
- Tests cover default init workspace diff, explicit `--worktree`, branch range, commit mode, `--all`, invalid mixed modes, and review rejecting target flags.
- Documentation includes concrete command examples for workspace diff, branch range, single commit, full repository, and subsequent `review` execution.
- `make check` passes.

## Out of Scope

- Adding target selection flags to `review-gauntlet review`.
- Implementing line-range-level diff slicing; this change scopes the review universe to changed files while review cells still review selected files through existing cell/rule mechanics.
- Automatically executing repeated review runs until a session is complete.
- Changing OCR-derived prompt/rule corpus behavior.
