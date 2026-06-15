# Design: run agents in the session worktree

## Classification

Requested artifact: implementation.

The proposal changes runtime command execution behavior for Git-worktree-backed `review-gauntlet run` sessions and adds tests/documentation to make that behavior explicit.

## Context model

A Git-worktree-backed run needs two roots:

- **Durable state root**: the base repository root that owns `.review-gauntlet/ledger.sqlite`, `active-session.json`, run artifacts, config, and checkpoint pointers.
- **Agent-facing root**: the linked session worktree recorded at `metadata.git_worktree.worktree_path`.

The command adapter should read and edit source files through the agent-facing root. Review Gauntlet should continue to record orchestration state through the durable state root.

## Execution rules

For non-Git-worktree sessions, existing behavior remains unchanged.

For Git-worktree-backed sessions:

1. Load active session metadata before invoking the command adapter.
2. Validate that `git_worktree.enabled` is `true`, `worktree_path` is present, and the resolved worktree path exists inside the base repository root.
3. Use the resolved worktree path as the command adapter's agent-facing root.
4. Expand command templates with:
   - `{repo_root}` = agent-facing root
   - `{state_dir}` = durable base `.review-gauntlet` state directory
   - `{prompt}` = existing generated ready prompt
5. Resolve default cwd to the agent-facing root.
6. Resolve configured `adapter.cwd` relative to the agent-facing root unless it is absolute, then require the resolved path to stay inside the agent-facing root.
7. Persist stdout/stderr/activity artifacts under the durable state directory as before.

## Safety and compatibility

The proposal deliberately avoids moving durable state into the linked worktree because that would require broader coordination across status, ready, review, finalize, TUI, and recovery flows. Keeping state in the base directory preserves existing commands while still making code reads/edits happen on the session branch.

The cwd constraint must use the agent-facing root rather than the durable root for Git-worktree sessions. This prevents adapter configs from accidentally or deliberately operating on the base worktree while still allowing nested cwd usage within the session worktree.

## Verification strategy

Tests should use a local command adapter fixture rather than a real agent. The fixture can write cwd/template evidence to a deterministic file or JSON artifact and then return success. This proves behavior without requiring opencode, credentials, or long-running agent work.
