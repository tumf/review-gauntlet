# Design: Session-scoped review cell ledger identity

## Premise / Context

- Review cell IDs are deterministic identifiers derived from `slice_id`, `rule_id`, and `file_path`.
- A repository can have multiple durable review sessions over time, and those sessions can legitimately include the same deterministic review cell.
- The ledger must preserve coverage per session because review completion depends on session-local coverage and finding state.
- Existing old-schema ledger migration is explicitly out of scope for this change.

## Decision

Use `(session_id, cell_id)` as the durable database identity for review cells, while preserving `cell_id` as the stable prompt-visible and adapter-visible review cell identifier.

This keeps deterministic cell IDs useful inside a session and avoids changing adapter fixtures, prompts, finding occurrences, or user-facing output formats. Session scoping belongs at the ledger boundary and in state mutation queries.

## Runtime Implications

- Session creation may insert the same deterministic `cell_id` for different `session_id` values.
- Coverage state mutations must include `session_id` to avoid cross-session writes.
- Active-session reads already filter by session via `list_cells(session_id)`, so the primary change is write-side scoping.
- Existing old-schema databases may still fail until removed and recreated; no automatic migration path is introduced.

## Alternatives Considered

### Generate globally unique cell IDs per session

Rejected. Adding the session ID into `cell_id_for()` would break the stable `RGC-...` identity used in prompts, fixtures, and deterministic ordering. It would also make cells less comparable across sessions.

### Replace old ledgers through automatic migration

Rejected for this change because the user explicitly requested no migration. SQLite primary key changes require table rebuild logic, which is unnecessary for the current scoped bug fix.

## Verification Strategy

- Unit tests for duplicate deterministic cell IDs across sessions.
- Unit tests for session-qualified cell state updates.
- Integration tests for repeated CLI initialization with overlapping review cells.
- Full `make check` to preserve formatting, lint, typecheck, and test behavior.
