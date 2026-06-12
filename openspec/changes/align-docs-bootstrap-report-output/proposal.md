---
change_type: implementation
priority: medium
dependencies: []
references:
  - .wt/setup
  - README.md
  - AGENTS.md
  - src/review_gauntlet/report.py
  - tests/test_cli.py
---

# Align Docs, Bootstrap, and Report Output

**Change Type**: implementation

## Problem/Context

Confirmed findings show user-facing polish and safety gaps: `.wt/setup` executes a mutable remote installer via `curl | sh`, README design text understates current implemented behavior, AGENTS smoke commands still use removed `--json`, and markdown report tables do not escape dynamic cell values.

Affected finding IDs include `RGF-0004`, `RGF-0013`, `RGF-0044`, `RGF-0047`, and `RGF-0049`.

## Proposed Solution

Make bootstrap behavior fail closed or verify pinned installer content, update documentation to match current CLI behavior, and escape markdown table cell values in report output.

## Acceptance Criteria

- `.wt/setup` no longer pipes a mutable remote installer directly into `sh` without pinning or verification.
- README Design text reflects the implemented session lifecycle and command adapter support.
- AGENTS smoke commands use `--format json` instead of removed `--json` flags.
- Markdown report output remains a valid table when dynamic evidence or IDs contain pipes or newlines.

## Explicit Completion Conditions

- `.wt/setup`, `README.md`, and `AGENTS.md` are updated with current, safe guidance.
- `src/review_gauntlet/report.py` escapes or normalizes markdown table cells.
- Tests cover report rendering with pipe and newline characters.
- `make check` passes.

## Out of Scope

- Introducing a new bootstrap dependency manager.
- Reworking report format away from markdown tables.
