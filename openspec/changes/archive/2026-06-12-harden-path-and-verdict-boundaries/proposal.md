---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/inventory.py
  - src/review_gauntlet/targets.py
  - src/review_gauntlet/config.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/findings.py
  - tests/test_inventory.py
  - tests/test_targets.py
  - tests/test_config.py
  - tests/test_command_review_adapter.py
  - tests/test_findings.py
---

# Harden Path and Verdict Boundaries

**Change Type**: implementation

## Problem/Context

Confirmed review findings show several trust-boundary gaps where repository paths, adapter configuration paths, review cell artifact paths, and adapter verdict comment paths are accepted too optimistically. This conflicts with the project constitution's requirement to be explicit, deterministic, and never hide unknown or invalid review state.

Affected finding IDs include `RGF-0003`, `RGF-0010`, `RGF-0014`, `RGF-0016`, `RGF-0021`, `RGF-0024`, `RGF-0029`, `RGF-0035`, `RGF-0040`, `RGF-0046`, and `RGF-0048`.

## Proposed Solution

Constrain all repository-relative inputs at the boundary where they enter review-gauntlet, and validate external adapter verdicts before they can affect findings or coverage. Reject absolute paths, parent traversal, symlink escapes, unsafe review-cell IDs, out-of-repository adapter cwd values, and verdict comments that do not target the evaluated review cell.

## Acceptance Criteria

- Target digest and file digest construction do not read symlinked files that resolve outside the reviewed repository.
- Target-scoped inventory creation rejects or skips absolute paths and parent-directory traversal before classification.
- `findings --path` rejects absolute paths and `..` traversal instead of silently treating them as normal filters.
- Explicit `--config` paths must resolve under the reviewed repository root.
- Command adapter artifact directories are confined under `.review-gauntlet/runs/<run_id>/cells/` even if a malformed cell ID is loaded.
- Command adapter `cwd` values must resolve under the reviewed repository root.
- Parsed verdict comments must refer to the current cell path and valid line ranges, while preserving OCR `0/0` imprecise comments.

## Explicit Completion Conditions

- Path validation behavior is implemented in `src/review_gauntlet/inventory.py`, `targets.py`, `config.py`, `cli.py`, `review_adapter.py`, and finding normalization as needed.
- Regression tests cover repository escape attempts, symlink escape attempts, invalid path filters, unsafe explicit config paths, unsafe cell IDs, unsafe adapter cwd values, cross-cell verdict comments, invalid line ranges, and valid OCR `0/0` comments.
- `make check` passes.
- Findings listed in the Problem/Context can be marked `fixed` after implementation and later verified by review.

## Out of Scope

- Changing the external command adapter transport model.
- Allowing out-of-repository adapter cwd or config paths as a documented feature.
- Modifying source files as part of proposal authoring.
