## Implementation Tasks

- [x] Update target modeling for explicit full-repository sessions and default workspace diff sessions. Completion condition: target metadata can distinguish workspace diff, branch diff, commit diff, and full repository sessions, and `review-gauntlet init` without target flags resolves to workspace diff. verification: unit - extend `tests/test_targets.py` for no-flag workspace default, explicit `--worktree`, `--all`, branch, commit, and invalid mixed target modes.
- [x] Implement diff-scoped review-universe file discovery for workspace, branch range, and commit targets. Completion condition: session initialization builds cells only for eligible changed files in diff modes and excludes unrelated unchanged tracked files. verification: integration - add CLI/session tests using temporary git repositories with staged, unstaged, untracked, branch-range, and commit-only changed files.
- [x] Preserve full-repository review through `init --all`. Completion condition: `review-gauntlet init --all` builds cells from the existing inventory behavior, including tracked files and eligible untracked files while preserving built-in exclusions such as `.review-gauntlet/`. verification: integration - add a CLI/session test that includes an unchanged tracked file in `--all` but excludes it from default workspace diff mode.
- [x] Keep `review-gauntlet review` target-option-free. Completion condition: `review` continues to consume only the active session and does not accept `--from`, `--to`, `--commit`, `--worktree`, or `--all`. verification: integration - add parser/CLI tests asserting those flags fail for `review` while `review` still advances one run for an initialized session.
- [x] Update user-facing documentation with OCR mapping and full-review mode. Completion condition: docs show `review-gauntlet init` + `review` equivalents for OCR workspace diff, branch range, commit review, and show `init --all` as review-gauntlet-only full repository review. verification: manual - inspect README examples and run documented smoke commands where external review execution can use fixtures.
- [x] Run the repository check suite. Completion condition: formatting, linting, type checking, and tests all pass. (verification: integration - `make check`).

## Future Work

- If users later need line-level diff-only prompts instead of changed-file review cells, propose that as a separate review cell slicing change.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate. Expected archive gate: `cflx openspec validate add-init-diff-and-all-targets --archive-gate`.
