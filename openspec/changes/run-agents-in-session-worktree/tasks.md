## Implementation Tasks

- [ ] Resolve the active Git-worktree execution context before each `review-gauntlet run` adapter step, including the linked session worktree path and the durable base state directory. (verification: integration - `uv run pytest tests/test_git_worktree_session.py` fails if a Git-worktree-backed run cannot identify its session worktree from session metadata)
- [ ] Execute Git-worktree-backed command adapter steps from the linked session worktree by default while keeping durable artifacts under the base `.review-gauntlet` state directory. (verification: integration - `uv run pytest tests/test_git_worktree_session.py` includes a command adapter that writes a marker file and fails if the file appears in the base root instead of `.review-gauntlet/worktrees/<session-id>`)
- [ ] Expand `{repo_root}` from the agent-facing session worktree root and `{state_dir}` from the base `.review-gauntlet` directory for Git-worktree-backed run steps. (verification: unit - `uv run pytest tests/test_cli_run.py tests/test_run_controller.py` fails if template expansion points both variables at the same root or moves `state_dir` into the session worktree)
- [ ] Resolve configured `adapter.cwd` relative to the agent-facing root for Git-worktree-backed sessions and reject cwd values that escape the linked session worktree. (verification: unit - `uv run pytest tests/test_cli_run.py` covers a valid nested cwd and an escaping cwd for Git-worktree-backed sessions)
- [ ] Preserve non-Git-worktree command adapter cwd and template behavior. (verification: integration - `uv run pytest tests/test_cli_run.py tests/test_run_controller.py` covers an ordinary session and fails if `{repo_root}` or default cwd changes for non-Git-worktree sessions)
- [ ] Preserve `finalize --merge` behavior after agent execution in the session worktree, including committing session branch changes and leaving base `.review-gauntlet` artifacts available. (verification: integration - `uv run pytest tests/test_git_worktree_session.py::test_finalize_merge_commits_merges_and_cleans_up` and a new run-to-merge scenario pass)
- [ ] Update user-facing documentation for the Git-worktree workflow so it states that `run` executes agents inside the linked session worktree while Review Gauntlet state remains in the base `.review-gauntlet` directory. (verification: integration - `python - <<'PY'\nfrom pathlib import Path\ntext = Path('README.md').read_text()\nassert 'session worktree' in text and '.review-gauntlet' in text\nPY` verifies `README.md` documents the split between agent cwd and durable state)
- [ ] Run focused verification and full checks after implementation. (verification: integration - `uv run pytest tests/test_git_worktree_session.py tests/test_cli_run.py tests/test_run_controller.py` and `make check` pass, or failures are documented with unrelated evidence)

## Future Work

- Consider a later migration that stores per-session state inside the linked worktree. This proposal intentionally avoids that migration and keeps state in the base `.review-gauntlet` directory.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate run-agents-in-session-worktree --archive-gate`
