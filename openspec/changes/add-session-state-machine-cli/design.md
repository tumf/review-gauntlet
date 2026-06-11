# Design: Session state machine CLI

## Current Architecture

The repository currently has a small pipeline:

```text
inventory.py -> planner.py -> report.py
```

`cli.py` exposes `inventory`, `plan`, and `report`. `models.py` defines immutable Pydantic models for file inventory, review slices, checks, matrix rows, and matrix completion.

The session design should preserve these pieces as the review-universe substrate rather than replacing them wholesale.

## Target Architecture

Introduce a session layer around the existing inventory/planner concepts:

```text
Target resolver
  -> Inventory
  -> ReviewPlan
  -> ReviewUniverse
  -> ReviewCells
  -> Session Ledger
  -> CLI commands
```

The core split is:

- Session: mutable aggregate state for the whole review effort.
- Run: immutable record for one `review-gauntlet review` invocation.
- Cell: current or historical `file x rule x slice` review unit.
- Finding: session-level issue identity and current triage state.
- Occurrence: a finding appearance in a specific run/cell.
- Event: human or external-system state transition evidence.

## Storage

Use `.review-gauntlet/` at the reviewed repository root:

```text
.review-gauntlet/
  active-session.json
  ledger.sqlite
  rules.lock
```

SQLite is preferred for the ledger because review sessions need append-only event history, occurrence history, and queryable status summaries. The implementation may keep typed Pydantic domain models at the boundary while storing normalized records internally.

## Target Modes

### Branch mode

`review-gauntlet init --from origin/main --to HEAD`

- `base_ref` is fixed for the session.
- `head_ref` may be `HEAD`.
- `head_mode` is `moving` unless explicitly fixed in a future extension.
- Each run records the current head OID and target digest.

### Worktree mode

`review-gauntlet init --worktree`

- The current working tree is the target.
- Each run records a worktree digest.
- Uncommitted changes are expected and should cause stale/pending reconciliation when they affect cells.

### Commit mode

`review-gauntlet init --commit abc123`

- The target is fixed.
- This mode is useful for coverage chunking, but not the primary N+1 fix/review loop.

## Review Command Boundary

`review-gauntlet review` must advance exactly one run. It may review multiple cells inside a single run according to budget, but it must not call itself again or loop until complete.

This boundary keeps the tool safe for humans, CI, bots, and separate LLM orchestrators that want to decide when to notify, wait, triage, fix, or retry.

## Finding Identity

Findings are session-level records. Each new adapter result is matched against existing findings by fingerprint before a new finding is created.

Fingerprint inputs should include stable semantic anchors:

- repository identity
- session base target
- file path
- rule id
- issue kind
- enclosing symbol when available
- normalized code anchor
- normalized claim

Line number alone must not define identity because edits can shift locations without changing the issue.

## Fixed Verification

A user marking a finding fixed is a claim, not proof. Therefore `mark <id> fixed` transitions to `fixed_pending_verification`.

A later review run verifies it by either:

- not detecting the same fingerprint again in the relevant current universe, or
- receiving explicit verifier evidence that the issue is fixed.

If the same fingerprint is detected again, the finding transitions to `reopened`.

## Completion Gate

A session can finalize only when both review work and finding handling are complete.

Required conditions:

- all current cells are terminal for the current universe
- no pending, stale, retry-needed, or failed cells remain
- all live findings are terminal
- no `fixed_pending_verification` findings remain
- no untriaged, confirmed, or reopened findings remain
- no expired waiver or accepted-risk finding remains
- current target digest matches the last reviewed target digest

`finalize` validates and records finalization; it does not run review work.

## Exit Codes

Keep existing usage error code 64.

MVP command status codes:

- 0: command succeeded and, where applicable, session is complete or action succeeded
- 1: session is incomplete or has blocking findings/finalization failures
- 2: internal/tool execution error
- 64: usage error

## Verification Strategy

Tests should avoid live LLM credentials. Use deterministic fake adapters and temporary repositories to verify real CLI behavior, ledger state, and state transitions.

Major verification ownership:

- unit: domain models, storage, fingerprinting, transitions, target validation
- integration: CLI flows against temporary repositories and SQLite ledger
- manual: smoke flow matching the documented human loop
