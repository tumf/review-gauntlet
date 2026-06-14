## Implementation Tasks

- [x] Add packaged preset resources for `claude`, `opencode`, and `codex`, and ensure they are included in installed package data (verification: integration - `uv run review-gauntlet config list` and `uv run review-gauntlet config show opencode` work from the package entrypoint without reading repository sample paths).
- [x] Implement config path helpers, preset lookup, JSONC loading, deep object merge, array replacement, and effective config resolution in `src/review_gauntlet/config.py` (verification: unit - `tests/test_config.py` covers project/global precedence, scalar override, deep object merge, and array replacement).
- [x] Change explicit config path resolution so absolute `--config` paths are accepted and relative paths resolve from the reviewed repository root, while missing or non-file paths fail actionably (verification: unit - `tests/test_config.py` covers absolute outside-repo config success and missing explicit config failure).
- [x] Add the `review-gauntlet config` parser group and implement `init`, `list`, `show`, `validate`, and recommended `effective` handlers in `src/review_gauntlet/cli.py` (verification: integration - CLI tests invoke each command through `main()` or `uv run review-gauntlet` and assert outputs/exit codes).
- [x] Implement `config init` output behavior for project config, global config, `--output`, `--force`, and `--dry-run` without adding a top-level `setup` command (verification: integration - `tests/test_cli_config.py` or equivalent CLI tests assert file creation paths, no-overwrite failures, forced overwrite, and dry-run no-write behavior).
- [x] Wire review and verify-fixes adapter loading to use effective config resolution while preserving `--fixture` behavior and existing command adapter validation (verification: integration - `tests/test_cli_session_review.py` and verify-fixes CLI tests exercise project config, global config, explicit absolute `--config`, and fixture bypass).
- [x] Replace the generic missing-adapter error with actionable missing-config guidance that lists project/global init commands and `config list` (verification: integration - `tests/test_cli_session_review.py` or equivalent CLI test asserts the no-config review failure message and usage-error exit status when no fixture/config is present).
- [x] Update README quick start and configuration documentation to describe clone-free `uvx review-gauntlet config init --preset opencode` and global setup flows (verification: manual - review `README.md` and run `uv run python -m pytest tests/test_cli.py` after documentation-adjacent CLI examples remain parser-valid where covered).
- [x] Add or update tests for `config validate` success/failure and `config effective` merged output (verification: integration - `tests/test_cli_config.py` or equivalent CLI tests parse JSON output when applicable or assert deterministic text output).

## Future Work

- `review-gauntlet doctor` can later check environment readiness, adapter availability, config resolution, and review matrix size.
- Repository-specific review surface, include/exclude, rule, coverage, and finalize-condition schema can be added in future proposals.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate. Expected archive gate: `cflx openspec validate add-config-system --archive-gate`.

## Acceptance #1 Failure Follow-up
- [x] Spec scenario 'Config init dry run has no side effects' (openspec/changes/add-config-system/specs/developer-workflow/spec.md:37-42) requires stdout to show 'the target path AND preset contents that would be written'. Implemented dry-run output for text mode to include the target path plus `--- config contents ---` and the bundled preset JSONC, added JSON dry-run `contents`, updated README dry-run wording, and verified with `uv run pytest tests/test_cli_config.py` (verification: integration - `uv run pytest tests/test_cli_config.py`).
