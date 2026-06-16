# Tasks: Run `.wt/setup` when a Git-worktree session is created

## Implementation Tasks

- [x] Add a structured setup-result type and runner in
  `src/review_gauntlet/git_worktree.py` (e.g. `WorktreeSetupResult` with
  `ran: bool`, `script_path: str`, `skipped_reason: str | None`,
  `returncode: int | None`, `warning: str | None`) and a
  `run_worktree_setup(worktree_root, *, enabled, timeout_seconds)` function that:
  resolves `<worktree_root>/.wt/setup`; returns a no-op result with
  `skipped_reason="missing"` when absent; returns a disabled result with
  `skipped_reason="disabled"` when `enabled` is false; otherwise runs the script
  with `cwd=worktree_root` and a generous timeout, capturing returncode and
  building a `warning` on non-zero exit / timeout / OS error (never raising).
  (verification: unit - `tests/test_git_worktree_session.py` exercises
  missing-script, disabled, success returncode 0, and non-zero-exit cases by
  pointing at temp worktrees with/without a fake executable `.wt/setup`.)

- [x] Invoke the runner from session creation: after `create_session_worktree`
  succeeds in `_cmd_init` (`src/review_gauntlet/cli.py:820-823`), call
  `run_worktree_setup` for the absolute worktree path, attach the result as the
  `setup` sub-object on both `output["git_worktree"]` and
  `metadata["git_worktree"]`, and persist via `store.create_session(metadata, cells)`.
  (verification: integration - `tests/test_init_targets.py` runs
  `init --git-worktree --format json` against a temp repo containing an
  executable `.wt/setup` and asserts the `git_worktree.setup` block reports
  `ran: true` and the script's observable side effect, e.g. a sentinel file it
  writes, exists in the worktree.)

- [x] Add the `--no-setup` flag to the `init` subparser
  (`src/review_gauntlet/cli.py:~187`) with help text, and thread its value into
  the `enabled` argument of `run_worktree_setup` (default: setup enabled).
  (verification: integration - `tests/test_init_targets.py` asserts
  `init --git-worktree --no-setup` yields `setup.ran == false` with
  `skipped_reason == "disabled"` and that the script's side-effect sentinel is
  absent in the worktree.)

- [x] Ensure no-op and warn-and-continue semantics end to end: absent
  `.wt/setup` yields success with `skipped_reason == "missing"`; a non-zero-exit
  `.wt/setup` yields a successful `init` (exit 0), preserves the worktree and
  session branch (`git worktree list` still shows it), and surfaces a `warning`
  plus the non-zero `returncode` in the `setup` block.
  (verification: integration - `tests/test_init_targets.py` covers both the
  missing-script success path and a failing `.wt/setup` that `exit 1`s, asserting
  init exit status is success, the worktree directory still exists, and
  `setup.warning` is populated. This path fails if the implementation rolls back
  the worktree or raises instead of warning.)

- [x] Confirm plain `init` (no `--git-worktree`) emits no `setup` block and does
  not execute `.wt/setup`.
  (verification: unit - `tests/test_init_targets.py` asserts a non-worktree
  `init` output has no `git_worktree` key, and therefore no `setup`.)

## Spec Tasks

- [x] Add the new requirement and scenarios under
  `openspec/changes/add-worktree-setup-hook/specs/review-sessions/spec.md`
  describing automatic setup, `--no-setup` opt-out, missing-script no-op, and
  warn-and-continue on failure.
  (verification: manual - `cflx openspec validate add-worktree-setup-hook
  --strict` passes; the requirement is new (ADDED), so no canonical heading edit
  is required.)

## Future Work

- Human decision on whether to later make the setup script path / command
  configurable via `config.jsonc` (currently Out of Scope).

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-worktree-setup-hook --archive-gate`
