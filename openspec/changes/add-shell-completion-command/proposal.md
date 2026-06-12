---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli.py
  - pyproject.toml
  - README.md
  - openspec/specs/developer-workflow/spec.md
---

# Add shell completion command

**Change Type**: implementation

## Problem / Context

Developers can install the `review-gauntlet` CLI locally through the existing `make install` workflow, but there is no first-class way to generate shell completion scripts for interactive shells. The CLI already centralizes command and option definitions in `src/review_gauntlet/cli.py`, so completion should derive from the same parser structure instead of duplicating command metadata in separate scripts.

The requested outcome is a shell completion command for the canonical `review-gauntlet` executable that helps users enable completions for common shells while preserving the existing parser behavior and usage-error semantics.

## Proposed Solution

Add a top-level `completion` subcommand to `review-gauntlet` that emits a shell completion script for a requested shell. The command should support at least `bash`, `zsh`, and `fish`, write the script to stdout, and exit before repository-root validation or session state access.

Use the existing argparse parser as the command source of truth where practical. If a small completion generator is needed, keep it deterministic and scoped to the existing command/option surface. Documentation should explain how to install or evaluate the generated completion script for each supported shell.

## Acceptance Criteria

- `review-gauntlet completion bash`, `review-gauntlet completion zsh`, and `review-gauntlet completion fish` print non-empty completion scripts to stdout and exit `0` without requiring a repository root.
- The generated scripts include completions for current top-level commands: `inventory`, `plan`, `report`, `init`, `review`, `verify-fixes`, `status`, `findings`, `mark`, `finalize`, and `completion`.
- The generated scripts include option completions for subcommands that expose options such as `--format`, `--budget`, `--concurrency`, `--fixture`, `--config`, `--audience`, `--finding`, `--path`, `--mark`, `--reason`, `--owner`, and `--until`.
- Unsupported shells fail with the existing usage-error behavior rather than printing a dummy script.
- Existing CLI behavior, including `--help`, `--version`, root validation, output formats, and invalid-option failures, remains compatible.
- README documents how to enable completion for supported shells using the installed `review-gauntlet` command.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` exposes and dispatches the `completion` subcommand before `Path(args.root)` or session-store logic is evaluated.
- Tests in `tests/test_cli.py` or a focused CLI test module prove success output for supported shells, parser rejection for unsupported shells, and no regression for existing command parsing behavior.
- README contains shell-specific completion setup instructions using `review-gauntlet completion <shell>`.
- `make check` passes after implementation.

## Out of Scope

- Adding dynamic completion for repository paths, finding IDs, session IDs, config keys, or values discovered from `.review-gauntlet` state.
- Adding completions for non-canonical aliases such as the typo `review-guantlet`.
- Publishing shell completion files as separate distribution artifacts.
- Changing the existing `make install` workflow or package entrypoint name.
