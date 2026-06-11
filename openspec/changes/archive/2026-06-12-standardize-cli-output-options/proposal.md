---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli.py
  - tests/test_cli_findings.py
  - tests/test_review_progress.py
  - openspec/specs/review-sessions/spec.md
---

# Standardize CLI Output Options

**Change Type**: implementation

## Problem/Context

`review-gauntlet` currently exposes inconsistent output option names across commands. Some session commands still use `--format human|json`, while legacy planning commands use `--format text|json`, `findings` already uses `text|json`, and `report` still exposes `--format markdown|json`. The `--audience human|agent` option is also registered on session commands that do not emit progress or audience-specific output.

This creates an inconsistent CLI contract for both humans and automation:

- `human` is not an output format; it should be represented as `text`.
- `markdown` should not remain a separate CLI format name when the project standard is text output.
- `--audience` should only exist where it changes progress/display behavior.

## Proposed Solution

Standardize output selection across the CLI:

- Commands that emit final output SHALL accept `--format text|json` where structured JSON is supported, defaulting to `text`.
- `--format human` SHALL be rejected everywhere.
- `--format markdown` SHALL be rejected for `report`; `report --format text` SHALL emit the existing Markdown-style report text.
- `--audience human|agent` SHALL be accepted only by commands that emit progress or audience-specific display output. In the current CLI, that is `review` only.
- `review --audience human` SHALL continue to emit progress to stderr, and `review --audience agent` SHALL continue to suppress that progress.

## Acceptance Criteria

- `inventory`, `plan`, `report`, `init`, `review`, `status`, `findings`, `mark`, and `finalize` expose `--format {text,json}` where they support JSON output, with `text` as the default.
- `report --format text` preserves the existing report body produced by the Markdown report renderer.
- `report --format markdown` fails with an argparse usage error.
- `--format human` fails with an argparse usage error for session commands that previously accepted it.
- `--audience` is visible and accepted for `review` only.
- `init`, `status`, `mark`, `finalize`, and `findings` reject `--audience` with an argparse usage error.
- `review --format json` continues to write parseable final JSON to stdout while human progress goes to stderr.
- `review --format json --audience agent` continues to suppress progress output.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` no longer registers `human` or `markdown` as `--format` choices.
- `src/review_gauntlet/cli.py` registers `--audience` only for the `review` command.
- Tests cover accepted help/output behavior and rejected obsolete options for affected commands.
- `make check` passes.
- `cflx openspec validate standardize-cli-output-options --strict` passes.

## Out of Scope

- Changing the shape or keys of existing JSON payloads.
- Changing the text contents of existing human-readable summaries beyond the CLI option vocabulary.
- Adding new output formats such as YAML, NDJSON, or rich terminal UI.
- Changing review session coverage, finding state, or adapter execution semantics.
