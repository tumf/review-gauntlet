---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/git_worktree.py
  - src/review_gauntlet/cli.py
  - openspec/specs/review-sessions/spec.md
---

# Run `.wt/setup` when a Git-worktree session is created

**Change Type**: implementation

## Problem / Context

`review-gauntlet init --git-worktree` creates a linked Git worktree under
`.review-gauntlet/worktrees/<session_id>` via `create_session_worktree`
(`src/review_gauntlet/git_worktree.py:72-86`). The function only runs
`git worktree add` and returns metadata — it never provisions the new worktree.

The repository ships a tracked bootstrap script `.wt/setup` (a `#!/bin/sh`
script that installs pre-commit / `prek` hooks for a fresh worktree). Because
`.wt/setup` is git-tracked, it is *checked out* into every new session worktree
but is **never executed**. As a result, agent steps that run inside the session
worktree (cwd is the linked worktree, per the existing "Git worktree sessions
SHALL isolate review work by session" requirement) start in an unprovisioned
worktree: hooks are not installed and any per-worktree setup the team relies on
is missing.

The user wants worktree creation to run `.wt/setup` automatically so a
`--git-worktree` session starts ready to use.

## Proposed Solution

After `git worktree add` succeeds during `init --git-worktree`, run the new
worktree's `.wt/setup` script with the working directory set to the linked
session worktree root. Behavior is governed by three confirmed decisions:

1. **Always-on with opt-out.** Setup runs by default on every
   `init --git-worktree`. A new `--no-setup` flag suppresses it.
2. **Warn and continue on failure.** If `.wt/setup` exits non-zero or times
   out, `init` still succeeds and the created worktree is preserved (no
   rollback). The failure is surfaced as a structured warning in the command
   output and recorded in session metadata.
3. **Fixed path, no-op when absent.** The script path is `.wt/setup` relative to
   the worktree root. If it does not exist, setup is a silent no-op (not an
   error).

The setup outcome is reported under the existing `git_worktree` output/metadata
block as a `setup` sub-object so callers and downstream tooling can see whether
provisioning ran, was skipped, or warned.

## Acceptance Criteria

- Running `review-gauntlet init --git-worktree` on a repo containing an
  executable `.wt/setup` executes that script with cwd equal to the newly
  created session worktree root, and the script's side effects (e.g. installed
  hooks) are present in the worktree afterward.
- The `git_worktree.setup` block in both JSON output and persisted session
  metadata records: whether setup ran (`ran`), the script path, a
  `skipped_reason` when not run, the process `returncode` when run, and a
  human-readable `warning` when it failed.
- `review-gauntlet init --git-worktree --no-setup` creates the worktree but does
  NOT execute `.wt/setup`; the `setup` block reports `ran: false` with
  `skipped_reason` indicating it was disabled.
- When `.wt/setup` is absent, `init --git-worktree` succeeds with the `setup`
  block reporting `ran: false` and a `skipped_reason` indicating the script is
  missing; exit status is success.
- When `.wt/setup` exits non-zero or times out, `init --git-worktree` still
  exits success, the worktree and session branch remain present (no rollback),
  and the `setup` block reports `ran: true` with the non-zero `returncode` and a
  `warning`.
- Setup is only attempted for `--git-worktree` sessions; plain `init` (no Git
  worktree) is unaffected and emits no `setup` block.

## Explicit Completion Conditions

A later agent/reviewer can confirm completion by verifying ALL of:

- `src/review_gauntlet/git_worktree.py` exposes a setup-runner (e.g.
  `run_worktree_setup`) returning a structured result type, and
  `create_session_worktree`/`_cmd_init` invoke it after worktree creation.
- `src/review_gauntlet/cli.py` registers an `init --no-setup` flag and threads
  its value into the setup decision; the `git_worktree.setup` block appears in
  init output and in stored metadata.
- New tests in `tests/test_git_worktree_session.py` (and/or
  `tests/test_init_targets.py`) cover: success path runs the script in the
  worktree, `--no-setup` skips it, missing-script no-op, and non-zero-exit
  warn-and-continue (worktree preserved).
- `cflx openspec validate add-worktree-setup-hook --strict` passes.

## Out of Scope

- Configurable setup script path or setup command via `config.jsonc` (fixed
  `.wt/setup` only for this change).
- Running `.wt/setup` for non-`--git-worktree` sessions or for the base
  checkout.
- Re-running setup on `run`/`finalize`, or any worktree re-provisioning after
  creation.
- Changing the contents/behavior of `.wt/setup` itself (it remains the
  team-owned bootstrap script).
- Rollback/cleanup of the worktree on setup failure (explicitly chosen
  warn-and-continue).
