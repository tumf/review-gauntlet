---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_findings.py
  - openspec/specs/review-sessions/spec.md
---

# Remove Findings Audience Option

**Change Type**: implementation

## Problem / Context

`review-gauntlet findings --help` currently exposes `--format {human,json}` and `--audience {human,agent}` because the command reuses shared session-output argument wiring. The `findings` command only emits a final findings summary and does not expose intermediate progress, so the audience switch does not control any meaningful behavior. The CLI also already uses `text` as the human-readable output name for legacy informational commands, making `human` inconsistent for this command.

## Proposed Solution

Give `findings` command-specific output arguments:

- `--format` accepts `text` and `json`.
- The default `--format` is `text`.
- `--audience` is not accepted for `findings`.
- Existing findings behavior remains unchanged: default output lists non-terminal findings, `--all` includes terminal findings, and JSON output remains machine parseable.

This is intentionally scoped to `findings`; other session commands keep their existing output contracts unless changed separately.

## Acceptance Criteria

- `review-gauntlet findings --help` shows `--format {text,json}`.
- `review-gauntlet findings --help` does not show `--audience`.
- `review-gauntlet findings` uses text output by default.
- `review-gauntlet findings --format json` emits parseable JSON with the existing findings payload.
- `review-gauntlet findings --format human` fails with an argparse usage error.
- `review-gauntlet findings --audience agent` fails with an argparse usage error.
- `review-gauntlet findings --all` continues to include terminal findings.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` defines findings-specific `--format` choices of `text` and `json`, defaulting to `text`, without adding `--audience` to the findings parser.
- Tests in `tests/test_cli_findings.py` or equivalent cover default text output, JSON output, help text, and rejection of removed/invalid options.
- `make check` passes.

## Out of Scope

- Changing `review`, `status`, `mark`, or `finalize` output arguments.
- Changing the findings ledger schema or finding state transitions.
- Changing the JSON payload shape for findings output.
