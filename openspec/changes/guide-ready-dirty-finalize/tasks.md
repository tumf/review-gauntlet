## Implementation Tasks

- [ ] Add dirty-finalize prompt classification to `ready` after all review and finding continuation work is exhausted. Completion condition: `src/review_gauntlet/cli.py` returns a commit/finalize prompt when `_finalize_reasons` contains only dirty review-universe and/or dirty non-review working-tree blockers. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_prompts_commit_when_finalize_blocked_by_dirty_git_changes`)

- [ ] Preserve `ready` no-task behavior for non-commit-resolvable finalize blockers. Completion condition: sessions blocked by missing review-run evidence, stale target digest evidence, expired decisions, or other non-dirty blockers still return `prompt: null` and exit `1`. (verification: unit - `uv run pytest tests/test_cli_ready.py::test_ready_outputs_no_ready_task_when_only_non_commit_blockers_remain`)

- [ ] Preserve `ready` priority order and read-only guarantees. Completion condition: existing actionable review/finding prompts still take precedence over dirty-finalize prompts, and `ready` does not mutate the ledger or checkpoint state. (verification: unit - `uv run pytest tests/test_cli_ready.py`)

- [ ] Run project checks. Completion condition: repository checks complete successfully without unrelated changes. (verification: integration - `make check`)

## Future Work

None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate guide-ready-dirty-finalize --archive-gate`
