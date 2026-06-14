---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/checkpoint.py
  - src/review_gauntlet/cli.py
  - tests/test_cli_finalize_checkpoint.py
  - openspec/specs/review-sessions/spec.md
---

# Hide Dirty Review-Universe Paths from Finalize Blockers

**Change Type**: implementation

## Problem / Context

`status` and `finalize` currently expose dirty review-universe file paths inside `finalize_blockers`, for example `review-universe files are dirty relative to HEAD: .github/workflows/ci.yml`. The blocker only needs to tell orchestrators and humans that review-universe files are dirty; listing individual paths is unnecessary noise for finalize-blocker output.

The dirty state itself must remain visible so completion cannot hide unreviewed or changed review-universe content.

## Proposed Solution

Change the dirty review-universe blocker text to a path-free stable message while preserving existing blocking behavior and commit-resolvable `ready` behavior.

The implementation should:

- Keep detecting dirty review-universe files using the existing git-based path collection.
- Keep failing `status`/`finalize` when review-universe files are dirty relative to `HEAD`.
- Emit a stable blocker message without appending file names.
- Keep non-review dirty blocker behavior unchanged unless explicitly changed by a later proposal.
- Update tests that currently assert dirty review-universe file names appear in `finalize_blockers`.

## Acceptance Criteria

- When review-universe files are dirty relative to `HEAD`, `status --format json` reports `can_finalize: false` and includes a review-universe dirty blocker that does not contain individual dirty file names.
- When review-universe files are dirty relative to `HEAD`, `finalize --format json` fails without writing or replacing latest checkpoint files and includes the same path-free blocker.
- `ready --format json` still treats dirty review-universe blockers as commit-resolvable and prompts the agent to commit intended git changes after review/finding work is exhausted.
- Dirty non-review files continue to use the existing non-review dirty blocker behavior.

## Explicit Completion Conditions

- `src/review_gauntlet/checkpoint.py` no longer formats `DirtyReviewUniverseError` with `self.paths` in the public blocker string.
- `src/review_gauntlet/cli.py` continues to classify the path-free review-universe dirty blocker as commit-resolvable for `ready`.
- `tests/test_cli_finalize_checkpoint.py` verifies that dirty review-universe blockers are present but do not include the dirty file name.
- Existing ready/finalize checkpoint tests pass, including dirty non-review behavior.
- `make check` passes.

## Out of Scope

- Hiding paths from non-review dirty blockers.
- Changing which files are classified as review-universe files.
- Changing dirty worktree detection, checkpoint writing, or session cleanup semantics.
