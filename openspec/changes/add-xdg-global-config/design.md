# Design: XDG global config discovery

## Classification

This is an implementation change. It changes runtime config discovery behavior for existing `review` and `verify-fixes` workflows while preserving the existing command adapter schema.

## Current Flow

`review` and `verify-fixes` call `load_config(root, args.config)`. `load_config` delegates path selection to `discover_config_path`, then reads JSONC and validates it as `ReviewGauntletConfig`.

Today, `discover_config_path` checks:

1. explicit `--config`, confined to the repository root
2. `.review-gauntlet/config.jsonc`
3. `.review-gauntlet/config.json`
4. `review-gauntlet.jsonc`
5. `review-gauntlet.json`

## Target Flow

Keep the current explicit and repo-local behavior unchanged, then append XDG fallback discovery:

1. `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`
2. `$XDG_CONFIG_HOME/review-gauntlet/config.json`

If `XDG_CONFIG_HOME` is unset or empty, the base directory is `Path.home() / ".config"`.

## Precedence Rationale

Repo-local config remains more specific than global config and must win. This avoids surprising repository-specific review behavior when a global adapter is configured for the developer's machine.

Explicit `--config` remains highest precedence because it represents an intentional per-invocation override.

## Safety

Global config discovery is read-only. It must not create directories or files, and it must not merge global settings with repository-local settings. The first discovered valid path is the only config file loaded.

## Verification Strategy

Unit tests should isolate `XDG_CONFIG_HOME` and home fallback using pytest monkeypatching so tests never depend on the real machine's `~/.config` contents.
