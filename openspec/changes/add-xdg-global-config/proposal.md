---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/config.py
  - src/review_gauntlet/cli.py
  - tests/test_config.py
  - README.md
---

# Add XDG global config discovery

**Change Type**: implementation

## Problem/Context

`review-gauntlet review` and `review-gauntlet verify-fixes` currently discover command adapter configuration only from explicit `--config` paths or repository-local files. Developers who use the same adapter configuration across repositories must copy `review-gauntlet.jsonc` into every repository or pass `--config` repeatedly.

The requested behavior is to support a global XDG config at `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`, defaulting to `~/.config/review-gauntlet/config.jsonc` when `XDG_CONFIG_HOME` is unset.

## Proposed Solution

Extend configuration discovery so repo-local configuration keeps the existing precedence, and global XDG configuration is used only as a fallback when no explicit or repo-local config exists.

Discovery order SHALL be:

1. explicit `--config <path>`
2. repo-local `.review-gauntlet/config.jsonc`
3. repo-local `.review-gauntlet/config.json`
4. repo-local `review-gauntlet.jsonc`
5. repo-local `review-gauntlet.json`
6. `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`
7. `$XDG_CONFIG_HOME/review-gauntlet/config.json`

The implementation SHALL read global config files only; it SHALL NOT create global config directories or files during discovery.

## Acceptance Criteria

- When no explicit or repo-local config exists, `load_config` discovers `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`.
- When `XDG_CONFIG_HOME` is unset, discovery falls back to `~/.config/review-gauntlet/config.jsonc`.
- Existing repo-local config precedence is preserved and overrides global config.
- Explicit `--config` remains highest precedence and keeps existing validation behavior.
- README documentation describes the full discovery order including global XDG fallback.

## Explicit Completion Conditions

- `src/review_gauntlet/config.py` contains a deterministic global config discovery path that respects `XDG_CONFIG_HOME` and `Path.home() / ".config"` fallback.
- `tests/test_config.py` covers XDG global fallback, repo-local-over-global precedence, and unset-`XDG_CONFIG_HOME` home fallback without relying on the developer machine's real home config.
- Existing CLI behavior remains compatible for `review` and `verify-fixes` because they continue to call `load_config(root, args.config)`.
- `README.md` documents the updated config discovery order.
- `make check` passes.

## Out of Scope

- Adding new CLI flags for global config management.
- Writing, initializing, or migrating config files.
- Merging repo-local and global config content; discovery selects exactly one config file.
