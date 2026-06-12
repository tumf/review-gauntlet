---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/inventory.py
  - tests/test_cli.py
  - tests/test_init_targets.py
  - openspec/specs/review-sessions/spec.md
---

# Fix plan command review exclusions

**Change Type**: implementation

## Problem / Context

The legacy `review-gauntlet plan` command builds a full project inventory and passes it directly to `build_plan`. That bypasses the existing review eligibility filter used by session initialization, so plan output can include files that review sessions intentionally exclude, such as `openspec/`, `tests/`, `docs/`, conventional test files, and package lock or manifest files.

This makes planning diagnostics disagree with actual review-session coverage and can overstate which files will be reviewed.

## Proposed Solution

Apply the existing `_review_inventory` filtering step to legacy planning outputs before constructing the plan used by `plan` and `report`.

The `inventory` command remains a general inventory diagnostic and continues to show project files subject only to artifact exclusions.

## Acceptance Criteria

- `review-gauntlet plan` excludes the same default review-path noise that `review-gauntlet init --all` excludes before creating review cells.
- `review-gauntlet report` builds its matrix from the filtered legacy plan, so excluded paths do not appear in report-derived planning output.
- `review-gauntlet inventory` remains unchanged and can still show package files and other non-artifact files in the general inventory.
- JSON output continues to use `model_dump_json(indent=2)` and remains parseable by existing tests.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` routes legacy `plan` and `report` plan construction through the existing review inventory filter.
- `tests/test_cli.py` includes regression coverage proving `plan` omits `docs/`, `openspec/`, conventional test paths, and package files while keeping eligible source files.
- Existing inventory tests continue to prove that `inventory` remains broader than review planning.
- Focused tests pass with `uv run pytest tests/test_cli.py tests/test_inventory.py tests/test_init_targets.py`.
- CI-equivalent verification passes with `make check`.

## Out of Scope

- Changing the underlying review exclusion rules in `inventory.py`.
- Adding new command-line flags to legacy `plan` or `report`.
- Changing session target selection or review-cell state semantics.
