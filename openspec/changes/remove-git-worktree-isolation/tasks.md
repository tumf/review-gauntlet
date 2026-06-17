# Tasks: remove-git-worktree-isolation

## Implementation Tasks

- [x] Remove `--git-worktree`, `--no-setup` from `init` parser in `src/review_gauntlet/cli.py` (`build_parser()`, lines 190-198). Remove `--merge` from `finalize` parser (line 296-302, keeping `--allow-non-review-dirty`). (verification: unit - `uv run pytest tests/test_cli.py` — new tests confirm `init --git-worktree` and `finalize --merge` produce usage error exit code 64)

- [x] Remove `review_gauntlet.git_worktree` import block (lines 42-47) and the `if bool(getattr(args, "git_worktree", False)):` block (lines 843-853) from `src/review_gauntlet/cli.py`. Remove `output["git_worktree"]` and `metadata["git_worktree"]` recording. (verification: unit - `uv run pytest tests/test_init_targets.py` — existing `plain_init_does_not_emit_or_run_setup` passes; new assertion confirms no `git_worktree` in JSON output)

- [x] Remove the `merge` branch (lines 2259-2355) from `_finalize` in `src/review_gauntlet/cli.py`. Retain the plain `finalize` path that calls `write_latest_checkpoint` without merge/cleanup. (verification: integration - `uv run pytest tests/test_cli_finalize_checkpoint.py::test_finalize_writes_checkpoint_files_and_cleans_active_session` passes; `finalize --merge` is a parse error)

- [x] Simplify `RunExecutionContext.from_active_session()` in `src/review_gauntlet/run_controller.py` to always return `cls(agent_root=root, state_dir=store.state_dir)` without inspecting `git_worktree` metadata. Remove the `worktree_error` reason and associated `ValueError` handling (lines 346-359). (verification: unit - `uv run pytest tests/test_run_controller.py` — updated/removed tests pass; stale `git_worktree` metadata does not trigger worktree_error)

- [x] Delete `src/review_gauntlet/git_worktree.py`. Ensure no production import references remain. (verification: integration - `uv run pytest tests/` passes; `grep "from review_gauntlet.git_worktree" src/review_gauntlet/` returns no results)

- [x] Remove `cleanup_git_worktree` from the `NEXT_ACTION_PRIORITY` map in `src/review_gauntlet/run_tui.py` (line 249). (verification: unit - `uv run pytest tests/test_run_tui.py` — updated `NEXT_ACTION_PRIORITY` test passes)

- [x] Remove Git-worktree-specific tests from `tests/test_git_worktree_session.py`. The entire file is usable for removal; keep only general-purpose test utilities if needed elsewhere. If deleting the file, verify no other test files import from it. (verification: integration - `uv run pytest tests/test_git_worktree_session.py` returns "no tests ran" after cleanup; remaining test suite passes)

- [x] Remove `--git-worktree`, `--no-setup`, `.wt/setup` related test functions from `tests/test_init_targets.py`: `test_init_git_worktree_runs_setup_and_persists_result`, `test_init_git_worktree_no_setup_skips_hook`, `test_init_git_worktree_missing_setup_is_successful_noop`, `test_init_git_worktree_setup_failure_warns_and_preserves_worktree`. (verification: unit - `uv run pytest tests/test_init_targets.py` passes with all remaining tests)

- [x] Remove or replace Git-worktree-specific run-controller tests from `tests/test_run_controller.py`: `test_run_execution_context_uses_git_worktree_agent_root`, `test_run_controller_passes_git_worktree_agent_root_to_command`, `test_run_execution_context_raises_for_missing_worktree_path` (line 537), the path-traversal test (line 563), `test_run_execution_context_raises_for_missing_worktree_directory` (line 576). Add a regression test confirming `RunExecutionContext.from_active_session` ignores stale `git_worktree` metadata and returns base `root` as `agent_root`. (verification: unit - `uv run pytest tests/test_run_controller.py` passes; stale-metadata-ignored test passes)

- [x] Add CLI regression tests: `init --git-worktree`, `init --no-setup`, `finalize --merge` all exit with usage error (exit code 64). (verification: unit - `uv run pytest tests/test_cli.py -k "git_worktree_rejected or no_setup_rejected or merge_rejected"` passes)

- [x] Run `make check` (format, lint, typecheck, test) and confirm the full suite passes. (verification: manual - `make check` exit code 0)

## Future Work

- Manual removal of stale `.review-gauntlet/worktrees/` directories and `review-gauntlet/RGS-*` branches left behind by previous sessions. These are inert after the feature removal and do not affect new sessions.

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate remove-git-worktree-isolation --archive-gate`
