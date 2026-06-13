---
change_type: implementation
priority: low
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli.py
  - openspec/specs/developer-workflow/spec.md
---

# Add CLI help defaults

**Change Type**: implementation

## Problem / Context

`review-gauntlet` defines defaults for many argparse options and optional positional arguments, but the current `--help` output omits those defaults. Developers reading command help must inspect source code or remember defaults for common flags such as `--format`, `--budget`, `--concurrency`, `--audience`, repeatable filters, and optional `root` arguments.

The requested outcome is to make CLI help self-describing whenever a parser-visible argument has a meaningful default value, while preserving existing argument parsing, command behavior, usage-error exits, and output schemas.

## Proposed Solution

Update the argparse declarations in `src/review_gauntlet/cli.py` so every command argument with an existing meaningful default includes that default in its help text. Keep the change focused on help text only: no accepted arguments, defaults, command dispatch, completion generation, or runtime output behavior should change.

Use concise default wording that matches the actual parser value or user-facing meaning:

- optional `root` positional arguments show `default: .`;
- `--format` shows `default: text`;
- numeric defaults show their integer value;
- boolean `store_true` flags show `default: false`;
- repeatable `append` filters with empty-list defaults show `default: none`;
- empty-string metadata fields show `default: none`.

## Acceptance Criteria

- `review-gauntlet <subcommand> --help` displays default values for parser-visible arguments that have meaningful defaults, including optional `root`, `--format`, `--budget`, `--concurrency`, `--audience`, `--finding`, `--path`, `--mark`, `--reason`, `--owner`, `--until`, `--all`, `--worktree`, and `--allow-non-review-dirty` where applicable.
- Help text for arguments without meaningful defaults, such as required positional IDs, `--fixture`, `--config`, `--from`, `--to`, `--commit`, `validate-verdict path`, and `completion shell`, is not forced to display misleading default text.
- Existing CLI parsing behavior remains unchanged: accepted arguments, default values, usage-error exit code `64`, JSON/text output behavior, session behavior, and shell completion option discovery continue to work as before.
- Tests assert representative help output contains default annotations and that existing completion/help behavior remains compatible.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` contains help text for all argparse actions with meaningful defaults listed in the acceptance criteria.
- Tests in `tests/test_cli.py` or another focused CLI test module exercise representative subcommands such as `inventory --help`, `review --help`, `verify-fixes --help`, `findings --help`, `mark --help`, and `status --help` and assert expected default annotations.
- Existing tests that parse stdout as JSON or text continue to pass without requiring output schema changes.
- `make check` passes after implementation.

## Out of Scope

- Changing any default values.
- Adding new CLI flags or subcommands.
- Replacing argparse with another CLI framework.
- Changing shell completion generation beyond preserving parser-visible option discovery.
- Updating README or user docs unless needed to keep existing documentation accurate.
