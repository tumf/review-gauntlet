---
change_type: implementation
priority: medium
dependencies: []
references:
  - Makefile
  - pyproject.toml
  - README.md
---

# Add Make Install CLI Target

**Change Type**: implementation

## Problem/Context

The package already declares the canonical console script `review-gauntlet` in `pyproject.toml`, so `uv tool install .` can create an installed CLI command from the local repository. However, the project `Makefile` has no `install` target, which makes the intended local install workflow less discoverable than the existing `make check`, `make test`, and hook targets.

The requested outcome is to install the correctly spelled `review-gauntlet` command via `make install`. The typo spelling `review-guantlet` must not be added as an alias.

## Proposed Solution

Add a minimal `install` target to the repository `Makefile` that runs `uv tool install .`, and include `install` in `.PHONY`. Document the local CLI install workflow in `README.md`, making it clear that installed usage is `review-gauntlet ...` while development usage can continue to use `uv run review-gauntlet ...`.

## Acceptance Criteria

- Running `make install` invokes `uv tool install .` from the repository root.
- The installed command name remains the canonical `review-gauntlet` console script declared in `pyproject.toml`.
- No `review-guantlet` console-script alias or documentation is introduced.
- README guidance explains how to install the CLI locally with `make install` and how to verify it with `review-gauntlet --help`.

## Explicit Completion Conditions

- `Makefile` contains a phony `install` target whose recipe is exactly the local uv tool install command for this package.
- `pyproject.toml` continues to expose `review-gauntlet = "review_gauntlet.cli:main"` and does not expose the typo alias.
- README contains a local install section or equivalent command guidance for `make install` and `review-gauntlet --help`.
- Manual verification records that `make install` completes successfully and that `review-gauntlet --help` runs after installation.

## Out of Scope

- Publishing the package to PyPI or another package index.
- Adding a `review-guantlet` typo alias.
- Changing CLI behavior, subcommands, review-session state, or adapter execution semantics.
