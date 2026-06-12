---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/__about__.py
  - src/review_gauntlet/cli.py
  - tests/test_cli.py
  - pyproject.toml
---

# Add Version Flag

**Change Type**: implementation

## Problem/Context

Developers and installed-tool users currently cannot ask the `review-gauntlet` CLI which package version is running. The version is already maintained in `src/review_gauntlet/__about__.py` and exported through the package, but `src/review_gauntlet/cli.py` only accepts subcommands and validates a repository root before dispatching normal command behavior.

The requested outcome is a lightweight top-level version display command that works without requiring an existing repository root or active review session.

## Proposed Solution

Add a top-level `--version` CLI flag that prints the command name and package version from `review_gauntlet.__about__.__version__`, then exits successfully before repository-root validation or subcommand handling. Keep the output simple and script-friendly: `review-gauntlet <version>` followed by a newline.

This is a single implementation proposal because the runtime CLI behavior and its regression test must ship together.

## Acceptance Criteria

- Running `review-gauntlet --version` prints `review-gauntlet <version>` to stdout using the package version defined in `src/review_gauntlet/__about__.py`.
- `review-gauntlet --version` exits with code `0` and does not require a positional root, existing repository directory, active session, adapter configuration, or any review state.
- The version flag does not change existing subcommand behavior for `inventory`, `plan`, `report`, `init`, `review`, `verify-fixes`, `status`, `findings`, `mark`, or `finalize`.
- Tests cover the success path and would fail if the implementation returned a dummy version, read an unrelated source of truth, or performed root/session validation before printing.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` imports the existing package version source and handles `--version` before any root path validation or session command dispatch.
- `tests/test_cli.py` includes a typed pytest case proving `main(["--version"])` prints `review-gauntlet 0.1.0` or the current imported `__version__` value and exits successfully.
- Existing CLI tests still pass, including parser rejection tests for obsolete flags and non-review audience flags.
- Repository checks pass with `make check`.

## Out of Scope

- Adding a `version` subcommand.
- Adding JSON output for version metadata.
- Changing package versioning, Hatch configuration, release workflows, or install behavior.
- Modifying review-session state, target selection, adapter execution, or finding workflows.
