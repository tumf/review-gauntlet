---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/config.py
  - tests/test_cli_findings.py
  - tests/test_config.py
  - .github/workflows/ci.yml
---

# Tighten CLI and Config Contract

**Change Type**: implementation

## Problem/Context

Confirmed findings show smaller but important contract issues: `findings --mark` can miss public hyphenated state names, environment variable names are under-validated, template literal brace behavior is ambiguous, and CI does not pin the intended Python runtime.

Affected finding IDs include `RGF-0002`, `RGF-0005`, `RGF-0007`, and `RGF-0042`.

## Proposed Solution

Align CLI filtering with public state names and persisted enum values, harden command adapter configuration validation, define literal brace handling in templates, and pin CI to Python 3.11 to match project guidance.

## Acceptance Criteria

- `findings --mark` correctly matches stored states for public values such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` when visibility rules allow them.
- Adapter env keys must be valid portable environment variable names.
- Template literal brace behavior is either supported with documented escaping or rejected with clear documentation and tests.
- CI setup installs Python 3.11 explicitly.

## Explicit Completion Conditions

- CLI mark filtering changes are implemented in `src/review_gauntlet/cli.py` with regression tests.
- Config validation changes are implemented in `src/review_gauntlet/config.py` with regression tests.
- `.github/workflows/ci.yml` pins Python 3.11.
- `make check` passes.

## Out of Scope

- Adding new template variables.
- Changing command adapter execution semantics beyond validation.
