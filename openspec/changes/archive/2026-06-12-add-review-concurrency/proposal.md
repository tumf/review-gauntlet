---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/review_cells.py
  - tests/test_cli_session_review.py
  - openspec/specs/review-sessions/spec.md
  - https://github.com/alibaba/open-code-review/blob/main/README.md
---

# Add Review Concurrency Control

**Change Type**: implementation

## Problem / Context

`review-gauntlet review` currently advances one session run by selecting eligible review cells and invoking the selected review adapter sequentially. This preserves deterministic coverage, but it underuses command adapters that spend most of their time waiting on subprocesses or external LLM calls.

Alibaba Open Code Review exposes `ocr review --concurrency` with default `8` as the maximum number of concurrent file reviews. `review-gauntlet` should provide an analogous control while preserving its ledger semantics: one review command creates exactly one run, `--budget` remains the selected-cell limit, and only successfully executed cells become `reviewed`.

## Proposed Solution

Add a `--concurrency N` option to the `review` command. The option limits how many selected review cells may execute through the adapter at the same time within a single run. The implementation should select the run's eligible cells deterministically first, up to `--budget`, then execute adapter work concurrently while applying ledger updates on the main control path in the selected-cell order.

The default concurrency should be `8` to match Alibaba OCR's documented default. Invalid values less than `1` should fail as usage errors before executing adapter work.

## Acceptance Criteria

- `review-gauntlet review --concurrency N` accepts positive integer values and rejects `N < 1` with usage error semantics.
- The default review concurrency is `8` when the option is omitted.
- `--budget` continues to cap the total selected cells for the run; concurrency only limits simultaneous adapter execution.
- The review command still creates exactly one run per invocation and does not loop until all pending cells are complete.
- Cell selection remains deterministic and follows the existing pending/stale/fixed-pending eligibility rules.
- Ledger writes, finding ID order, and status output remain deterministic even when adapter execution is concurrent.
- Only cells whose adapter review succeeds are marked `reviewed`; failed cells remain pending or stale.
- On adapter failure, the command exits non-zero with `failed_cell_id`, `error`, `failure`, and status fields equivalent to the existing failure contract.
- Command adapter artifacts remain isolated per cell and are safe to produce concurrently.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` exposes `--concurrency` for the `review` subcommand and validates it before adapter execution.
- Review cell selection is computed once per run from the reconciled current review universe and respects `--budget` before parallel execution starts.
- Adapter calls for selected cells can run concurrently, but `SessionStore` mutations and finding normalization/upserts occur deterministically on the main path.
- Regression tests cover default/explicit concurrency parsing, invalid values, budget interaction, deterministic output ordering, success behavior, and failure behavior.
- `make check` passes.

## Out of Scope

- Passing `--concurrency` through to a nested external adapter command automatically.
- Adding process-level or distributed workers.
- Changing review cell identity, finding fingerprinting, or target selection behavior.
- Changing Alibaba OCR's own CLI behavior.
