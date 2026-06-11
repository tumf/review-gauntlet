---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/inventory.py
  - src/review_gauntlet/targets.py
  - tests/test_inventory.py
  - tests/test_init_targets.py
  - openspec/specs/review-sessions/spec.md
  - https://github.com/alibaba/open-code-review/tree/c323c6b40c72aa95d7cb801bedcb957b52ff9807
---

# Add OCR-Inspired File Filtering

**Change Type**: implementation

## Problem / Context

`review-gauntlet` currently excludes its own generated state, common Python cache/build artifacts, editor metadata, and files ignored by Git-backed discovery. That keeps the inventory small for Python projects, but it does not yet reflect several practical exclusion layers used by Alibaba `open-code-review`:

- repository/vendor dependency directories such as `vendor/`, `node_modules/`, and `target/`
- build/package staging directories such as `_packages/`, `rpm/`, and `pkgs/`
- frontend/mobile generated directories such as `.happypack/`, `.cachefile/`, and `oh_modules/`
- default review exclusions for test/spec/documentation directories (`tests/`, `docs/`, `openspec/`) and test-file patterns that should reduce review cell noise without deleting those files from the general inventory model

The constitution requires deterministic scope and visible coverage. File filtering therefore needs to be explicit, testable, and separated by responsibility instead of hidden inside an LLM prompt.

## Proposed Solution

Extend review-universe filtering with an OCR-inspired model split into two responsibilities:

1. **Project artifact filtering**: expand the existing built-in generated/dependency directory exclusions used by inventory and target-scoped inventory construction.
2. **Review-default filtering**: add a deterministic path-pattern layer for files that should remain classifiable in inventory when appropriate, but should not become default review cells unless future configuration explicitly opts them back in.

Use the OCR default patterns as the baseline reference, while adapting behavior to `review-gauntlet`'s coverage model. The implementation should keep Git ignored-file behavior intact and continue using bounded Git subprocess calls.

## Acceptance Criteria

- Full repository inventory and target-scoped inventory exclude OCR-inspired generated/dependency directories: `vendor/`, `node_modules/`, `target/`, `.happypack/`, `.cachefile/`, `_packages/`, `rpm/`, and `pkgs/`.
- Review cell generation excludes `openspec/`, `tests/`, and `docs/` by default, plus OCR default test-path patterns including common Go, Java, Kotlin, Rust, JavaScript/TypeScript, Python, Ruby, ETS, and `oh_modules` test/generated paths.
- The default review-path exclusion does not silently remove source files that do not match those directories or patterns.
- Existing `.gitignore` / `--exclude-standard` behavior remains unchanged for Git-backed discovery.
- `target_digest()` and `file_digests()` use the same review-universe exclusions that determine review cells, so generated/dependency/test-default paths do not unnecessarily stale review coverage.
- The implementation exposes the default filters through named constants or helpers so future include/exclude configuration can override or extend them without duplicating pattern logic.
- Tests cover both filesystem fallback inventory and Git-backed target/session behavior.

## Explicit Completion Conditions

This proposal is complete when:

- `src/review_gauntlet/inventory.py` or an extracted filtering module contains deterministic helpers for artifact and default review exclusions.
- Review cell construction paths used by `init --all`, default/worktree init, branch init, commit init, `target_digest()`, and `file_digests()` all use the appropriate shared helper instead of ad hoc `.review-gauntlet` checks.
- Unit/integration tests assert excluded generated/dependency directories do not appear in inventory or review cells.
- Unit/integration tests assert `openspec/`, `tests/`, `docs/`, and OCR-style test-file patterns are omitted from review cells by default while normal source files still produce cells.
- `make check` passes.

## Out of Scope

- Adding user-configurable include/exclude rule files.
- Implementing an extension allowlist for review cells.
- Changing review adapter prompts or OCR rule documents.
- Changing the semantics of Git ignored files beyond existing `--exclude-standard` behavior.
