---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - openspec/changes/archive/2026-06-15-add-git-worktree-session-finalize/design.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/git_worktree.py
  - src/review_gauntlet/config.py
  - tests/test_git_worktree_session.py
  - tests/test_cli_run.py
  - tests/test_run_controller.py
---

# Run agents in the session worktree

**Change Type**: implementation

## Problem / Context

`review-gauntlet init --git-worktree` creates a linked session worktree and session branch, but `review-gauntlet run` currently invokes the external command adapter from the base repository execution context unless the adapter config supplies a `cwd`. In the observed session, metadata recorded `git_worktree.enabled: true` and a valid `.review-gauntlet/worktrees/<session-id>` path, yet the agent attempted source inspection against the base repository path rather than the isolated session worktree.

This weakens the purpose of Git-worktree-backed sessions: branch/worktree isolation exists, but the agent execution path that reads and edits source files is not required to use it. The existing archived design also says Git-worktree sessions should create session state in the session worktree root, while the current implementation keeps durable Review Gauntlet state in the base `.review-gauntlet` directory. To minimize risk, this change keeps durable review state in the base state directory and switches only the agent-facing repository root/cwd to the session worktree.

## Proposed Solution

For active sessions with `metadata.git_worktree.enabled: true`, `review-gauntlet run` SHALL execute external command adapter steps with the session worktree as the agent-facing repository root. The base `.review-gauntlet` directory remains the durable state and artifact location.

The command template and cwd rules become:

- `{repo_root}` resolves to the session worktree root for Git-worktree-backed run steps.
- `{state_dir}` continues to resolve to the base repository `.review-gauntlet` state directory.
- If `adapter.cwd` is omitted, the command runs in the session worktree root.
- If `adapter.cwd` is present, it is resolved relative to the agent-facing root and must remain inside the session worktree for Git-worktree-backed sessions.
- Non-Git-worktree sessions preserve the current behavior: `{repo_root}` and default cwd are the base repository root, and `adapter.cwd` is constrained inside that root.

This proposal does not move the SQLite ledger, run artifacts, active-session marker, or checkpoint state into the session worktree. It only aligns the external agent's filesystem view with the linked worktree created for the session.

## Acceptance Criteria

- A Git-worktree-backed `review-gauntlet run` invokes the configured adapter with `cwd` equal to the linked session worktree when no adapter cwd is configured.
- In that Git-worktree-backed run step, `{repo_root}` expands to the linked session worktree path while `{state_dir}` expands to the base repository `.review-gauntlet` directory.
- If `adapter.cwd` is configured for a Git-worktree-backed session, it is resolved relative to the linked session worktree and rejected if it escapes that worktree.
- Source reads and edits performed by the external agent during a Git-worktree-backed run affect the session branch/worktree rather than the base worktree.
- Run artifacts, command stdout/stderr logs, ledger state, active-session marker, and checkpoint state remain under the base repository `.review-gauntlet` directory.
- `finalize --merge` continues to commit intended session branch changes from the linked session worktree and merge them into the recorded base branch.
- Non-Git-worktree sessions retain their existing cwd/template behavior and path-safety validation.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/run_controller.py` and/or `src/review_gauntlet/cli.py` carries enough active-session Git-worktree metadata into command execution to select an agent-facing root distinct from the durable state root.
- `_run_session_command_step` or an equivalent helper expands `{repo_root}` from the agent-facing root and `{state_dir}` from the durable state directory.
- `_resolve_session_cwd` or an equivalent helper constrains configured adapter cwd inside the agent-facing root for Git-worktree-backed sessions.
- `tests/test_git_worktree_session.py` includes an integration test where a command adapter writes or reads a file and proves the operation occurs in `.review-gauntlet/worktrees/<session-id>` rather than the base root.
- `tests/test_cli_run.py` or `tests/test_run_controller.py` covers template expansion for `{repo_root}` and `{state_dir}` in Git-worktree and non-Git-worktree sessions.
- Focused tests `uv run pytest tests/test_git_worktree_session.py tests/test_cli_run.py tests/test_run_controller.py` pass.
- `make check` passes, or any failure is documented with evidence that it is unrelated.

## Out of Scope

- Moving the review ledger, active-session marker, run artifacts, or checkpoints into the session worktree.
- Changing `review-gauntlet review` single-step semantics.
- Changing target-selection behavior for `init --worktree` or `init --git-worktree`.
- Changing branch naming, worktree path naming, merge strategy, or cleanup behavior beyond what is needed to execute agents inside the existing session worktree.
- Fixing TUI failure reason wording or timeout labeling; that is covered separately by `normalize-run-agent-failure-display` and existing `clarify-run-finalize-timeout` work.
