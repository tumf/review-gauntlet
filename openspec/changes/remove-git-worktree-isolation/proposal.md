---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/git_worktree.py
  - src/review_gauntlet/run_tui.py
  - tests/test_git_worktree_session.py
  - tests/test_init_targets.py
  - tests/test_run_controller.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# remove-git-worktree-isolation

**Change Type**: implementation

## Problem/Context

`review-gauntlet init --git-worktree` creates a Git linked worktree under `.review-gauntlet/worktrees/<session-id>`, runs `.wt/setup` as a hook, and persists `git_worktree` metadata in the session. `review-gauntlet run` then switches the agent cwd to the linked worktree. `review-gauntlet finalize --merge` commits, merges, and `git worktree remove`/`git branch -d` on completion.

The application should not operate Git linked worktrees at all. The `--git-worktree` feature, its runtime agent-root switching, its setup hook execution, and its merge/cleanup lifecycle must be removed.

`--worktree` (workspace-diff target selection) is NOT affected — it has never created or removed Git linked worktrees; it only selects which files to review.

## Proposed Solution

1. **Remove `init --git-worktree` and `--no-setup`** from the CLI. `review-gauntlet init --git-worktree` becomes a usage error (argparse rejects the unknown flag).
2. **Remove `finalize --merge`** from the CLI. `review-gauntlet finalize --merge` becomes a usage error.
3. **Remove all worktree creation, setup execution, metadata recording, and branch merge** from the init/finalize code paths.
4. **Simplify `RunExecutionContext`** so it never inspects `git_worktree` metadata — `agent_root` is always the base repository root.
5. **Remove `src/review_gauntlet/git_worktree.py`** — the entire module is dead production code after the above changes.
6. **Remove or replace Git-worktree-specific tests** with regression tests verifying the removed flags are rejected.
7. **Remove `cleanup_git_worktree`** from the TUI next-action map.
8. **Update canonical spec** to remove three REMOVED requirements, modify two existing requirements to drop `finalize --merge` references.

## Acceptance Criteria

- `review-gauntlet init --git-worktree` exits with usage error (exit code 64).
- `review-gauntlet init --no-setup` exits with usage error.
- `review-gauntlet finalize --merge` exits with usage error.
- `review-gauntlet init --all --format json` output never includes `git_worktree` key; session metadata never includes `git_worktree`.
- `review-gauntlet run` always uses the base repository root as agent cwd / `{repo_root}`, regardless of any stale `git_worktree` metadata in existing sessions.
- No `git worktree add`, `git worktree remove`, `git branch -d`, or `.wt/setup` execution is reachable from any production code path.
- `init --worktree` target selection works unchanged.
- Existing plain `finalize` (without `--merge`) works unchanged.
- `make check` passes (format, lint, typecheck, test).
- Canonical spec no longer mandates Git linked worktree isolation.

## Explicit Completion Conditions

- [ ] `grep "git_worktree\|create_session_worktree\|merge_session_worktree\|cleanup_session_worktree\|run_worktree_setup\|merge_preflight_blockers" src/review_gauntlet/` returns zero matches, OR remaining matches are only in comments/dead-code notices.
- [ ] `uv run pytest tests/` passes with all Git-worktree tests removed or re-targeted.
- [ ] `make check` passes.
- [ ] `cflx openspec validate remove-git-worktree-isolation --strict` passes.

## Out of Scope

- Changing `--worktree` workspace-diff target selection behavior.
- Removing `.wt/setup` bootstrap documentation from `openspec/specs/review-sessions/spec.md` Scenario "Worktree setup does not pipe latest installer to shell" (that scenario describes general developer practice, not review-gauntlet behavior).
