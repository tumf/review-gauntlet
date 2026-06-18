## Implementation Tasks

- [ ] Update default `init` target fallback in `src/review_gauntlet/cli.py` so plain `review-gauntlet init` uses ALL when no usable latest checkpoint is present. (verification: integration - `tests/test_init_targets.py` asserts no-checkpoint plain init records target kind `all` and includes eligible unchanged tracked files plus eligible current files)

- [ ] Add target metadata and resolution behavior for checkpoint-derived default sessions to include worktree changes in addition to checkpoint-base-to-HEAD committed changes. (verification: unit - `tests/test_targets.py` exercises a branch-like target with worktree inclusion and proves the returned path set is the union of committed diff, staged, unstaged, and untracked paths)

- [ ] Update `src/review_gauntlet/checkpoint.py::target_from_latest_checkpoint` or equivalent default-target construction so latest-checkpoint defaults opt into worktree inclusion while preserving checkpoint validation failures. (verification: integration - `tests/test_init_targets.py` asserts invalid latest checkpoint still exits with the existing validation error and does not create an all-files session)

- [ ] Preserve explicit target flag behavior for `--from/--to`, `--commit`, `--worktree`, and `--all`. (verification: integration - `tests/test_init_targets.py` asserts explicit `--from/--to` excludes uncommitted changes, explicit `--worktree` excludes unrelated committed/unchanged files, and explicit `--all` still uses full inventory)

- [ ] Update existing default-init tests whose expectations mention worktree fallback so they reflect the new all-files fallback and checkpoint-plus-worktree default. (verification: unit - focused `uv run pytest tests/test_init_targets.py tests/test_targets.py` passes)

- [ ] Run repository checks after implementation. (verification: integration - `make check` passes)

## Future Work

- None.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate update-init-default-target --archive-gate`
