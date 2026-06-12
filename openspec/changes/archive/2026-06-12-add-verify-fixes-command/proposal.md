---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/review_adapter.py
  - tests/test_cli_session_review.py
  - tests/test_cli_findings.py
  - openspec/specs/review-sessions/spec.md
---

# Add Verify Fixes Command

**Change Type**: implementation

## Problem/Context

Developers can currently mark a finding as fixed with `review-gauntlet mark <finding-id> fixed`, which records `fixed_pending_verification`. The existing `review` command can include fixed-pending paths during normal review selection, and the ledger already supports `fixed_verified` and `reopened` transitions. However, there is no explicit command for the common workflow: after a developer fixes findings, run only the relevant re-review work and report whether the findings are now verified.

This creates operational ambiguity. A developer has to infer that another `review` invocation is the correct verification mechanism, and that invocation may also select unrelated pending or stale cells. The requested outcome is a dedicated command that makes fix verification explicit while preserving the constitution rules that reviewed means executed, fixed is not terminal until verified, orchestration remains external, and unknown or failed verification remains visible.

## Proposed Solution

Add `review-gauntlet verify-fixes` as a focused review-session command for re-reviewing findings in `fixed_pending_verification`.

The command should reuse the existing command adapter, prompt generation, verdict validation, run artifacts, fingerprint normalization, and finding transition logic rather than creating a parallel review engine. It should select only current review cells needed to evaluate fixed-pending findings, optionally filtered by finding ID or path, and then report which findings became `fixed_verified`, which reopened, and which remain unverifiable because their current cells could not be evaluated.

The command should support the same execution controls as `review` where they are relevant: `--config`, `--fixture`, `--budget`, `--concurrency`, `--format text|json`, and `--audience human|agent`. It should also support focused verification filters: repeatable `--finding <finding-id>` and repeatable `--path <repo-relative-path-or-prefix>`. Repeated filters within a family are ORed; different families are ANDed.

## Acceptance Criteria

- `review-gauntlet verify-fixes --config review-gauntlet.jsonc` evaluates only fixed-pending findings from the active session and does not select unrelated pending, stale, confirmed, untriaged, reopened, or terminal findings.
- When a targeted fixed-pending finding's path is successfully reviewed and the same fingerprint is not seen, the finding transitions to `fixed_verified` with a ledger event.
- When a targeted fixed-pending finding is detected again during verification, the finding transitions to `reopened` with a ledger event and is not also marked `fixed_verified` in the same run.
- The command exits `0` when every targeted fixed-pending finding is either verified and no adapter cell failed, or there were no matching fixed-pending findings to verify.
- The command exits `1` when any targeted finding reopens, any targeted finding remains fixed-pending because its path was not successfully evaluated, or any selected verification cell fails.
- The command emits structured JSON with at least `run_id`, `reviewed_cells`, `targeted_finding_ids`, `fixed_verified_ids`, `reopened_ids`, `unverifiable_ids`, `finding_ids`, `can_finalize`, and `finalize_blockers` when `--format json` is requested.
- `--finding` filters select exact finding IDs and reject IDs that do not refer to fixed-pending findings in the active session with an actionable usage error or structured no-match result that does not mutate state.
- `--path` filters use the same repository-relative safety semantics as `findings --path`; absolute paths and parent traversal fail with a usage error before adapter execution.
- `--budget 0` performs a safe no-op that creates no run, mutates no finding state, and reports matching targeted findings as still requiring verification.
- Help and README guidance make this the documented command for post-fix re-review.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` registers `verify-fixes` and routes it through a dedicated command handler rather than overloading `findings` or requiring users to run generic `review` for this workflow.
- Verification selection code derives current review cells from the active session target and limits selected cells to paths for targeted `fixed_pending_verification` findings, respecting `--budget` and `--concurrency`.
- `SessionStore` exposes repository-verifiable helpers for listing fixed-pending findings under filters and for producing the final verification result without bypassing existing transition validation.
- The command adapter path remains shared with `review`, preserving existing artifact locations, prompt generation, output-mode handling, verdict validation, and cancellation behavior.
- Tests cover success verification, redetection reopening, selected-cell failure leaving targeted findings unverifiable, `--budget 0` no-op behavior, `--finding` and `--path` filters, unsafe path rejection, help output, JSON shape, and non-selection of unrelated review cells.
- `README.md` documents `verify-fixes` as the command to run after developers mark findings fixed.
- Repository checks pass with `make check`.

## Out of Scope

- Automatically applying source fixes or asking the adapter to modify code.
- Auto-looping until all fixed findings are verified.
- Changing finding fingerprint semantics, finding IDs, or allowed terminal states.
- Replacing the existing `review` behavior that can verify fixed-pending findings when their paths are selected.
- Adding bulk `mark` operations, CI integration, notifications, or developer assignment workflows.
- Verifying findings that no longer map to a current review cell because the target path has been removed or is no longer review-eligible; those should remain visible as unverifiable or require a separate triage decision.
