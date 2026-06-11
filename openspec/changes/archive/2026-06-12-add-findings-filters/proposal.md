---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_findings.py
  - openspec/specs/review-sessions/spec.md
---

# Add Findings Filters

**Change Type**: implementation

## Problem/Context

`review-gauntlet findings` currently lists open findings by default and only supports `--all` to include terminal findings. During triage and fix work, users need to extract focused subsets such as confirmed findings for a specific file without writing ad hoc JSON filtering scripts.

The current session exposed this gap while reviewing and triaging findings: after marking decisions, the practical next step was to list only `confirmed` findings and often group them by `path` for implementation planning.

## Proposed Solution

Extend `review-gauntlet findings` with narrow, non-mutating filters:

- Add `--path <repo-relative-path-or-prefix>` to filter findings by repository-relative path.
- Add `--mark <mark>` to filter findings by triage/finding mark, using user-facing mark vocabulary.
- Allow repeated `--path` and repeated `--mark`; repeated values within the same option family are ORed, while different option families are ANDed.
- Preserve the existing default of hiding terminal findings unless `--all` is provided.
- Preserve existing text and JSON output shapes after filtering.

## Acceptance Criteria

- `review-gauntlet findings . --mark confirmed --format json` returns only confirmed findings from the active session.
- `review-gauntlet findings . --path src/review_gauntlet/config.py --format json` returns only findings whose `path` is exactly that file or is under that prefix when a directory-style prefix is provided.
- Repeating `--mark` returns findings matching any requested mark, for example `--mark confirmed --mark reopened`.
- Repeating `--path` returns findings matching any requested path or path prefix.
- Combining `--path` and `--mark` applies both filters.
- Terminal findings remain hidden by default even when requested by `--mark`; `--all` includes terminal findings before applying filters.
- `findings --help` documents the new filters and still does not expose `--audience`.
- Existing `findings` default behavior and JSON payload shape remain compatible for callers that do not pass filters.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` registers `--path` and `--mark` for the `findings` subcommand.
- The findings query/filtering path applies default terminal suppression, optional path filters, and optional mark filters deterministically without modifying review coverage or finding state.
- `tests/test_cli_findings.py` covers mark-only, path-only, combined, repeated-filter, terminal-without-`--all`, and `--all` terminal filter behavior.
- CLI help tests prove the new filters are visible while `--audience` remains rejected for `findings`.
- `make check` passes.
- `cflx openspec validate add-findings-filters --strict` passes.

## Out of Scope

- Adding bulk `mark` operations or mutating findings from the `findings` command.
- Adding fuzzy text search, rule filters, sorting, pagination, or field projection.
- Changing finding IDs, stored finding states, ledger schema, or mark transition rules.
- Changing the existing JSON object keys emitted by `findings`.
