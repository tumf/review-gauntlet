# Design: Findings Filters

## Scope

This change extends only the read-only `findings` command. It does not alter finding state transitions, review execution, coverage reconciliation, or ledger schema.

## Filter Semantics

Filtering should be deterministic and simple:

- Start from active-session findings.
- If `--all` is absent, remove terminal findings using the existing terminal set.
- Apply `--mark` filtering if provided.
- Apply `--path` filtering if provided.
- Emit the same text or JSON payload shape as today.

Repeated values within the same filter are ORed. Different filter kinds are ANDed. This matches common CLI expectations and keeps implementation small.

## Mark Vocabulary

The option is named `--mark` because users think in terms of triage marks when preparing fix work. Internally it maps to persisted finding states. The accepted values should remain user-facing and hyphenated where appropriate, for example `false-positive`, `accepted-risk`, `fixed-pending-verification`, and `fixed-verified`.

The output should continue to show persisted state strings exactly as it does today. This avoids a breaking JSON contract change.

## Path Matching

`--path` values are repository-relative strings. A value that names a file matches that file exactly. A value that is directory-style, such as `src/review_gauntlet/`, matches findings under that prefix.

Implementation may normalize leading `./` and repeated separators for comparison, but should not resolve against the host filesystem or require paths to exist. Findings are historical ledger data, and filtering should work even if a file has since moved or been deleted.

## Non-Goals

Bulk mutation is intentionally excluded. A later proposal can add safe bulk operations if needed, but this change only makes the existing ledger easier to inspect.
