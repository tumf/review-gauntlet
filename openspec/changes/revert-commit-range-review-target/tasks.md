# Tasks: Revert Commit-Range Review Target

## Implementation Tasks

- [ ] 1. Restore `TargetKind.WORKTREE` and `TargetKind.ALL` in `targets.py`. Revert enum to include both members. verification: `grep "WORKTREE\|ALL" src/review_gauntlet/targets.py` shows both members.

- [ ] 2. Restore `_workspace_changed_files()` function in `targets.py`. Handles staged, unstaged, and untracked files via `git diff --name-only --cached`, `git diff --name-only`, and `git ls-files --others --exclude-standard`. verification: unit — `tests/test_targets.py::test_workspace_changed_files` (restored).

- [ ] 3. Restore `resolve_target()` to accept `worktree` parameter and return WORKTREE as default. Parameter modes: `all_files` → ALL, `commit` → COMMIT, `base_ref+head_ref` → BRANCH, else → WORKTREE. verification: unit — `tests/test_targets.py` resolve_target tests.

- [ ] 4. Restore WORKTREE and ALL cases in `changed_files_for_target()`. WORKTREE returns `_workspace_changed_files(root)`, ALL returns `None` (full inventory). verification: unit — `tests/test_targets.py` changed_files tests.

- [ ] 5. Remove `file_digests_at_commit()`, `_review_universe_files_at_commit()`, and `_git_bytes()` from `targets.py`. Simplify `_git()` back to text-mode only. verification: grep — no references to removed functions in `src/`.

- [ ] 6. Restore `--worktree` CLI argument in init parser (cli.py). Add `--worktree` action="store_true" to init subparser. verification: unit — `tests/test_cli.py::test_cli_init_worktree_accepted` (restored).

- [ ] 7. Restore `worktree` kwarg to `resolve_target()` call in `_cmd_init()` (cli.py ~805). Pass `worktree=args.worktree`. verification: integration — `tests/test_cli_session_review.py` init with `--worktree` test.

- [ ] 8. Remove `_review_head_commit()` function from cli.py. Remove the `review_head_commit` variable from `_cmd_init()`. verification: grep — `_review_head_commit` not in `src/`.

- [ ] 9. Revert `_cmd_init()` init_digests to `file_digests(root)`. Remove `review_head_commit` from metadata dict. verification: unit — `tests/test_cli_session_review.py` init output does not include `review_head_commit`.

- [ ] 10. Revert init default target to WORKTREE (cli.py ~815). When no explicit target and no checkpoint, use `TargetSpec(kind=WORKTREE)`. verification: integration — `tests/test_init_targets.py` default target tests.

- [ ] 11. Simplify `_file_digests_for_session()` to always return `file_digests(root)`. Remove `_metadata_review_commit()` function. verification: unit — `tests/test_cli_session_review.py` digest tests.

- [ ] 12. Remove `review_commit` from review prompts in cli.py. Remove the parameter from `_review_cell_ready_prompt()`, `_finding_ready_prompt()`, `_partial_ready_prompt()`, and their callers. verification: unit — `tests/test_cli_ready.py` prompt tests — no `review_commit` in output.

- [ ] 13. Remove `review_commit` from `review_adapter.py`. Remove from `PromptContext`, `build_review_prompt()` signature, `_review_commit_prompt_lines()` function, `ExternalCommandReviewAdapter.__init__()` and `_read_cell_content()`. verification: unit — `tests/test_review_adapter.py` — no `review_commit` in prompt output.

- [ ] 14. Revert `ExternalCommandReviewAdapter._read_cell_content()` to read from working tree. Remove the `git show` path; use `Path.read_bytes()` directly. verification: unit — `tests/test_review_adapter.py` content reading tests.

- [ ] 15. Update all affected test expectations. Remove `review_head_commit` assertions, restore `--worktree` acceptance tests, fix digest-based tests to use working tree digests. verification: `make test` — all tests pass.

- [ ] 16. Run full CI: `make check`. Covers format-check, lint, typecheck, and test. verification: manual — `make check` exits 0.

## Future Work

- Remove the archived proposal directory `openspec/changes/archive/2026-06-18-review-commit-range/` (manual cleanup after revert is merged).

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate revert-commit-range-review-target --archive-gate`
