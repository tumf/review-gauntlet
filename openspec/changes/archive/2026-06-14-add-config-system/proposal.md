---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/config.py
  - configs/review-gauntlet-opencode.jsonc
  - configs/review-gauntlet-codex.jsonc
  - configs/review-gauntlet-claude.jsonc
  - README.md
  - tests/test_config.py
---

# Add bundled config presets and effective config resolution

**Change Type**: implementation

## Problem / Context

Review Gauntlet currently requires users to provide a command adapter configuration before review execution, but the documented starter flow relies on files under the source repository's `configs/` directory. This makes `uvx review-gauntlet` insufficient for first-time setup because users cannot create a starter config without either cloning the repository or copying a config from external documentation.

The current config loader also discovers a single config file rather than resolving an effective configuration from built-in defaults, global user preferences, project review plans, and explicit CLI overrides. Repository-local configuration takes precedence over global configuration, but there is no user-facing command group for initializing, listing, showing, or validating packaged config presets.

## Proposed Solution

Add a `review-gauntlet config` command group that provides the only configuration-generation command, `config init`, plus preset inspection and validation commands. Bundle the `claude`, `opencode`, and `codex` starter presets inside the installed package so `uvx review-gauntlet config init --preset opencode` works without cloning the repository.

Update config resolution so review commands can build an effective config from built-in defaults, global config, project config, and explicit `--config`. Preserve deterministic merge semantics: objects deep merge, scalars use the last writer, and arrays replace. Allow explicit `--config` to point to either repository-relative paths or absolute paths outside the repository.

Update README quick start to lead with `uvx review-gauntlet config init --preset opencode`, while retaining contributor/source-install documentation separately.

## Acceptance Criteria

- Users can create a project config using `uvx review-gauntlet config init --preset opencode` without cloning the repository.
- Users can create a global config using `review-gauntlet config init --global --preset opencode` at the resolved XDG/fallback config path.
- `config init` supports `--preset`, `--global`, `--force`, `--dry-run`, and `--output` with safe overwrite behavior.
- `config list` prints exactly the bundled preset names `claude`, `opencode`, and `codex`.
- `config show <preset>` prints the bundled preset contents to stdout without requiring repository state.
- `config validate` validates discovered effective configuration, and `config validate --config <path>` validates an explicit file.
- Explicit `--config` accepts absolute paths as well as repository-relative paths and fails actionably if the path does not exist or is not a file.
- Effective config resolution applies precedence in this order: CLI explicit config/options, project config, global config, built-in defaults.
- Effective config merging deep-merges objects, replaces arrays, and lets later scalars win.
- When review execution needs an adapter config and none is available, the CLI prints an actionable message pointing to `config init --preset opencode`, `config init --global --preset opencode`, and `config list`.
- README quick start no longer requires cloning the repository or copying files from `configs/` to obtain starter configuration.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` exposes the `config` command group and routes each MVP subcommand with existing usage-error exit behavior.
- `src/review_gauntlet/config.py` provides packaged preset lookup, config path helpers, JSONC validation, deep merge, effective config resolution, and explicit absolute-path config support.
- Packaged preset files or package-data resources are included for `claude`, `opencode`, and `codex`, and are available from installed/uvx execution.
- Existing review and verify-fixes adapter loading use the effective config resolver and preserve fixture behavior.
- Tests cover preset listing/showing/init behavior, dry-run and force behavior, global/project precedence, deep merge rules, array replacement, explicit absolute `--config`, missing config guidance, and validation failures.
- README quick start and config documentation are updated to describe the clone-free `uvx` flow and global setup flow.
- `make check` passes.

## Out of Scope

- Adding a top-level `setup` command.
- Adding a `custom` preset.
- Implementing `review-gauntlet doctor`.
- Adding repository-specific review rule, coverage, or finalize-condition schema beyond fields already supported by this change.
- Changing review session state transitions, finding triage semantics, or OCR rule behavior.
