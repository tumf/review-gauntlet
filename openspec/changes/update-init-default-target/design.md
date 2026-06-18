# Design: Update init default target selection

## Current Behavior

Plain `review-gauntlet init` computes `explicit_target` from the presence of target flags. When no explicit target is present, `_cmd_init()` selects `target_from_latest_checkpoint(root)` or falls back to a WORKTREE `TargetSpec`.

`target_from_latest_checkpoint()` validates the latest checkpoint and returns a BRANCH target from the checkpoint `review_base_commit` to `HEAD`. `changed_files_for_target()` handles BRANCH by running `git diff --name-only <base> <head>`, which excludes staged, unstaged, and untracked worktree files.

## Target Model

The implementation should distinguish an explicit branch target from a checkpoint-derived default target that also includes worktree changes. A small field on `TargetSpec`, such as `include_worktree: bool = False`, is the preferred model because it keeps the target deterministic and visible in session metadata.

Expected semantics:

| Target source | Target kind | Includes committed diff | Includes staged/unstaged/untracked | Full inventory |
| --- | --- | --- | --- | --- |
| plain init with checkpoint | BRANCH + worktree inclusion metadata | yes | yes | no |
| plain init without checkpoint | ALL | n/a | current files included by inventory | yes |
| explicit `--from/--to` | BRANCH | yes | no | no |
| explicit `--worktree` | WORKTREE | no | yes | no |
| explicit `--all` | ALL | n/a | current files included by inventory | yes |
| explicit `--commit` | COMMIT | commit files only | no | no |

## Path Collection

For checkpoint-derived defaults, changed path collection should union:

- `git diff --name-only <checkpoint-base> <HEAD>`
- `_workspace_changed_files(root)` result, covering staged, unstaged, and untracked non-ignored paths

The union should continue through existing safe path and review inclusion filters by returning relative paths to `_build_target_plan()`.

If workspace path collection fails in the checkpoint-derived default path, the safest behavior is to return `None` from `changed_files_for_target()` so `_build_target_plan()` falls back to full inventory rather than silently dropping uncommitted changes.

## Validation and Compatibility

Invalid checkpoint handling remains strict because checkpoint presence indicates the user intended continuation from a known review base. The new all-files fallback only applies when no latest checkpoint exists.

Explicit flags remain stable and are not retargeted by this change. This preserves existing automation that intentionally requests branch-only or worktree-only review.
