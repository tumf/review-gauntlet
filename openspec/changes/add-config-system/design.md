# Design: Config system and bundled presets

## Overview

The change introduces a small configuration lifecycle around the existing command adapter configuration:

1. package-bundled starter presets
2. user/project config file creation through `config init`
3. validation and inspection commands
4. effective config resolution for review execution

The design keeps `config init` as the only config-generation command and avoids adding `setup`.

## Config scopes

Review Gauntlet resolves configuration from these conceptual layers, lowest to highest precedence:

1. built-in defaults
2. global config
3. project config
4. explicit CLI config/options

Global config is for user-specific defaults such as adapter command configuration and output preferences. Project config is for repository-specific review behavior and should be committable. For this implementation, the existing adapter schema remains supported while resolution and initialization are prepared for future top-level sections.

## Paths

Global preferred path:

- `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`

Global fallback path:

- `~/.config/review-gauntlet/config.jsonc`

Project preferred path:

- `.review-gauntlet/config.jsonc`

Project compatibility path:

- `review-gauntlet.jsonc`

Existing `.json` discovery may remain as backward compatibility, but the generated and documented path is JSONC.

## Explicit `--config`

Explicit `--config` is an override and may be:

- absolute, including outside the repository
- relative, resolved against the reviewed repository root

The resolved file must exist and be a regular file. Explicit config bypasses project/global discovery for file selection while still using built-in defaults as the base for model defaults and future default sections.

## Merge semantics

Effective config construction uses deterministic merge rules:

- objects: deep merge
- scalars: later source wins
- arrays: later source replaces the earlier array

This avoids surprising global/project array concatenation for review rule lists or future include/exclude lists.

## Preset packaging

The bundled presets are:

- `claude`
- `opencode`
- `codex`

They should be stored as package data or importlib resources so they are available in installed and `uvx` executions. The repository-level `configs/` examples may continue to exist, but the CLI must not depend on reading them from the source tree.

## CLI behavior

`config` subcommands should not require an active review session. Commands that only inspect presets should not require a repository root. Commands that validate discovered project/global config may default root to `.` using the same root semantics as other commands when project config is involved.

`config init --dry-run` should print enough information to prove what would be written and where, without creating directories or files.

## Validation strategy

MVP validation includes JSONC parsing, schema validation, adapter command validation, template variable validation, and explicit path checks. Review-surface/rule/coverage validation should only be enforced when those schema fields exist; until then, they remain future extension points.

## Backward compatibility

Existing users with `.review-gauntlet/config.jsonc` or `review-gauntlet.jsonc` continue to work. Existing explicit repo-relative `--config` continues to work. The main intentional compatibility change is that absolute `--config` paths are now accepted rather than rejected.
