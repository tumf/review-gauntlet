---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/config.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/targets.py
  - tests/test_command_review_adapter.py
  - tests/test_cli_session_review.py
  - tests/test_targets.py
---

# Fix Adapter Output and Root Digest Edge Cases

**Change Type**: implementation

## Problem/Context

The remaining confirmed review findings are concentrated around command adapter failure/output handling: unexpected adapter exceptions are not converted into structured review failures, nested file-json output paths do not get parent directories created, and `output.path` can still depend on `{prompt}` even though prompt construction and verdict reading resolve output paths at different times.

During verification, `review-gauntlet status --format json` also failed when root was omitted because target digest paths mixed an absolute resolved review-universe path with the original relative root `.`. That root handling issue prevents normal default-root CLI usage and should be fixed with the same review execution correctness pass.

Affected finding IDs: `RGF-0011`, `RGF-0023`, `RGF-0025`, and `RGF-0026`.

## Proposed Solution

Tighten command adapter execution so all adapter failures return through the existing structured failure path, file-json output destinations are prepared after containment validation, and `adapter.output.path` cannot use `{prompt}`. Normalize target digest and file digest root handling so relative and absolute roots behave consistently.

## Acceptance Criteria

- Unexpected exceptions raised by adapter work are captured as `ReviewAdapterError` results with structured failure details, not raw tracebacks.
- `review` preserves the existing partial-success semantics when an unexpected adapter exception occurs in one selected cell.
- File-json output paths nested under the cell artifact directory have their parent directories created before the external command is invoked.
- `adapter.output.path` rejects `{prompt}` at config validation time, while `{prompt}` remains valid for adapter `args` and `env`.
- The prompt's `verdict_output_file` and the adapter's actual file-json read path cannot diverge because of prompt-dependent output path expansion.
- `review-gauntlet status --format json` works with the default root `.` and with an equivalent absolute root.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` catches unexpected adapter exceptions in concurrent review execution and reports them through the structured failed-cell output path.
- `src/review_gauntlet/config.py` or equivalent config validation rejects `{prompt}` in `adapter.output.path` without removing support for `{prompt}` in `args`/`env`.
- `src/review_gauntlet/review_adapter.py` creates nested output parent directories after output containment validation and before command invocation.
- `src/review_gauntlet/targets.py` computes digest-relative paths against a resolved repository root, regardless of whether the caller passed `.` or an absolute path.
- Tests cover all acceptance criteria with runnable unit or integration checks.
- `make check` passes.

## Out of Scope

- Changing the command adapter transport contract beyond output path validation and directory preparation.
- Adding a new review adapter type.
- Automatically marking findings fixed; the review session ledger must still require explicit `mark` and later verification.
