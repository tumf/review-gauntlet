---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/inventory.py
  - tests/test_inventory.py
  - .gitignore
---

# Exclude generated and ignored files from inventory

**Change Type**: implementation

## Problem / Context

`review-gauntlet` builds its review universe from inventory output. That universe currently includes `.review-gauntlet/` session artifacts such as run prompts, command metadata, verdict files, and ledger outputs when those files are present but not ignored by Git. This inflates review cells with tool-generated state instead of project source files.

The fallback filesystem walk also relies on a small hardcoded ignored-directory list and does not cover common cache/build/editor artifacts such as `.ruff_cache/`, `.pyright/`, `.mypy_cache/`, `build/`, `dist/`, `.idea/`, or `.vscode/`. This weakens the product principle that coverage is a precise, explicit representation of the intended review surface.

## Proposed Solution

Tighten inventory discovery so generated review state, cache directories, build artifacts, editor metadata, and ignored files do not enter the review universe.

- Always exclude `.review-gauntlet/` from inventory results, even if it is not listed in `.gitignore`.
- Extend deterministic fallback exclusions for common cache, build, coverage, virtualenv, and editor artifacts.
- Ensure the Git-backed listing path applies the same built-in exclusions after `git ls-files --cached --others --exclude-standard` returns paths.
- Add `.review-gauntlet/` to repository `.gitignore` so normal self-review state stays ignored by Git.
- Preserve inclusion of tracked/source files and existing file classification behavior for legitimate project files.

## Acceptance Criteria

- `.review-gauntlet/` and all files below it are excluded from `review-gauntlet inventory`, `plan`, `report`, `init`, and `review` universe generation.
- Git-backed inventory continues to respect Git ignore rules via `--exclude-standard` and also applies review-gauntlet's built-in exclusions.
- Fallback recursive inventory excludes common generated directories and files, including `.review-gauntlet/`, `.ruff_cache/`, `.pyright/`, `.mypy_cache/`, `build/`, `dist/`, `wheels/`, `*.egg-info/`, `.coverage`, `htmlcov/`, `.DS_Store`, `.idea/`, and `.vscode/`.
- Legitimate tracked project files such as Python source, tests, CI workflows, docs, and configuration files remain included and classified as before.
- Self-review artifact creation no longer increases subsequent inventory cell counts.

## Explicit Completion Conditions

- `src/review_gauntlet/inventory.py` has a shared inclusion predicate used by both Git-backed and fallback file discovery.
- Built-in exclusion rules cover `.review-gauntlet/` and common cache/build/editor artifacts without relying solely on repository `.gitignore` contents.
- `.gitignore` includes `.review-gauntlet/` so generated session state is ignored in normal Git workflows.
- `tests/test_inventory.py` includes regression coverage proving `.review-gauntlet/` and representative cache/build/editor artifacts are excluded while normal project files remain classified.
- A Git-backed test or integration path verifies ignored/untracked generated files are not returned by inventory discovery.
- `make check` passes.

## Out of Scope

- Implementing a complete standalone `.gitignore` parser for non-Git fallback mode.
- Changing review cell identity, coverage state transitions, or finding reconciliation semantics.
- Removing existing `.review-gauntlet/` files from a developer's local working tree.
- Changing command adapter artifact persistence paths.
