## ADDED Requirements

### Requirement: Review SHALL support parallel cell execution in Phase 1

`review-gauntlet review` SHALL execute all pending review cells in parallel during Phase 1. Each cell's review adapter invocation SHALL be read-only with respect to the repository. Successful cells SHALL transition to `REVIEWED` state. Failed cells SHALL remain `PENDING` for retry. The `--parallel N` option SHALL control the maximum number of concurrent adapter invocations, defaulting to the number of available CPU cores.

#### Scenario: All pending cells reviewed in parallel

**Given**: an active session with 5 pending review cells
**When**: the developer runs `review-gauntlet review`
**Then**: all 5 cells are reviewed concurrently
**And**: successful cells are marked `REVIEWED`
**And**: findings from all cells are persisted with state `open`
**And**: the command exits 0 when all cells succeed

#### Scenario: Partial failure preserves coverage

**Given**: an active session with 3 pending review cells
**And**: one adapter invocation fails with an unexpected error
**When**: `review-gauntlet review --format json` completes
**Then**: the 2 successful cells are marked `REVIEWED`
**And**: the failed cell remains `PENDING`
**And**: findings from successful cells are persisted
**And**: the command exits non-zero with structured failure details

#### Scenario: Zero pending cells is a no-op

**Given**: an active session where all cells are already `REVIEWED`
**When**: the developer runs `review-gauntlet review`
**Then**: no new run record is created
**And**: no adapter commands are invoked
**And**: the command exits 0

### Requirement: Resolve SHALL handle finding judgment and fix in a single step

`review-gauntlet resolve` SHALL execute Phase 2: grouping all `open` findings by file path and invoking a resolution agent per file group. The resolution agent SHALL determine each finding as `confirmed` or `dismissed` and, for confirmed findings, apply the corresponding code fix. The agent SHALL output a verdict.json with `resolutions` declaring the final state of each finding.

#### Scenario: Resolution agent confirms and fixes findings

**Given**: an active session with 2 open findings for `src/app.py`
**When**: `review-gauntlet resolve` invokes the resolution agent for `src/app.py`
**And**: the agent outputs verdict.json with `verdict: finish` and `resolutions: [{finding_id: "RGF-0001", state: "confirmed"}, {finding_id: "RGF-0002", state: "dismissed", dismiss_reason: "not applicable"}]`
**Then**: `RGF-0001` transitions to `confirmed`
**And**: `RGF-0002` transitions to `dismissed` with `dismiss_reason: "not applicable"`

#### Scenario: Resolution agent requires continuation

**Given**: an open finding for `src/complex.py`
**When**: the resolution agent outputs verdict.json with `verdict: continue` and `next_turn_instructions: "need to also update imports"`
**Then**: the agent is re-invoked with the previous context and new instructions
**And**: the finding remains `open` until a finish verdict is received

#### Scenario: Resolution agent aborts

**Given**: an open finding for `src/broken.py`
**When**: the resolution agent outputs verdict.json with `verdict: abort` and `error: "cannot determine fix approach"`
**Then**: the finding remains `open`
**And**: the command reports the abort with the error message
**And**: other file groups continue processing independently

### Requirement: Resolve SHALL support parallel file-grouped execution in Phase 2

`review-gauntlet resolve` SHALL execute resolution agents for different file paths concurrently. Findings on the same file path SHALL be handled by a single agent invocation to prevent file write conflicts. The `--parallel N` option SHALL control the maximum number of concurrent file-group agents.

#### Scenario: Non-conflicting files resolved in parallel

**Given**: open findings for `src/a.py` and `src/b.py`
**When**: `review-gauntlet resolve --parallel 2` runs
**Then**: resolution agents for `src/a.py` and `src/b.py` execute concurrently
**And**: both files can be modified independently without conflict

#### Scenario: Single-file findings handled sequentially

**Given**: 3 open findings all on `src/app.py`
**When**: `review-gauntlet resolve` runs
**Then**: all 3 findings are handled by a single agent invocation
**And**: the agent receives all 3 finding contexts in one prompt

### Requirement: Session SHALL progress through two sequential phases

A review session SHALL progress through two sequential phases: Phase 1 (review) where all pending cells are reviewed to produce findings, and Phase 2 (resolve) where all open findings are resolved. The session SHALL NOT interleave review and resolution. Finalization SHALL only be possible after both phases complete.

#### Scenario: Phase 1 must complete before Phase 2 begins

**Given**: an active session with pending cells and open findings
**When**: the developer runs `review-gauntlet resolve`
**Then**: the command reports that Phase 1 is incomplete
**And**: no resolution agents are invoked

#### Scenario: Session is finalizable after both phases

**Given**: an active session with all cells `REVIEWED`
**And**: all findings are `confirmed` or `dismissed`
**And**: review-universe files are clean relative to HEAD
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: finalization succeeds
**And**: checkpoint files are written

## MODIFIED Requirements

### Requirement: Review cells SHALL model coverage independently from finding state

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows. Review cells SHALL transition only from `PENDING` to `REVIEWED`. The `STALE` and `SUPERSEDED` states are removed. File content changes between session initialization and review SHALL NOT trigger automatic state transitions on existing cells.

#### Scenario: Unknown review cell update fails

**Given**: a session ledger without cell `RGC-missing`
**When**: internal reconciliation attempts to update `RGC-missing`
**Then**: the store raises an actionable lookup error
**And**: no caller can treat the missing cell as updated coverage

#### Scenario: Review cell transitions are PENDING to REVIEWED only

**Given**: an active session with a pending review cell
**When**: the cell is successfully reviewed
**Then**: the cell state is `REVIEWED`
**And**: no other state transitions are possible for the cell

### Requirement: Finding triage SHALL be explicit and event-backed

Finding triage SHALL transition findings from `open` to either `confirmed` (fix applied) or `dismissed` (not a valid issue). Triage event metadata SHALL be validated before persistence. Dismissed findings SHALL include a `dismiss_reason`. Both `confirmed` and `dismissed` are terminal states.

#### Scenario: Finding transitions from open to confirmed

**Given**: an active session with an open finding
**When**: the resolution agent determines the finding is valid and applies a fix
**Then**: the finding transitions to `confirmed`
**And**: the transition is recorded as a finding event

#### Scenario: Finding transitions from open to dismissed

**Given**: an active session with an open finding
**When**: the resolution agent determines the finding is a false positive
**Then**: the finding transitions to `dismissed`
**And**: the `dismiss_reason` is recorded in the finding metadata
**And**: the transition is recorded as a finding event

### Requirement: Ready command SHALL emit the next skill-directed prompt

`review-gauntlet ready` SHALL emit the next skill-directed prompt from concrete renderable work items. It SHALL preserve deterministic priority: pending review cells, then open findings, then finalize readiness. Stale review cells are removed; no stale-related prompts are generated.

#### Scenario: Ready priority uses new two-phase order

**Given**: an active session with pending review cells and open findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the prompt targets pending review cells (Phase 1)
**And**: open findings are not selected while pending cells exist

#### Scenario: Ready selects open findings after all cells reviewed

**Given**: an active session with all cells reviewed and open findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the prompt targets open findings (Phase 2)

#### Scenario: Ready selects finalize when both phases complete

**Given**: an active session with all cells reviewed and all findings terminal
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the prompt is the finalize prompt

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL execute Phase 1: reviewing all pending review cells in a single invocation. A review invocation with no pending cells SHALL NOT create a run record. `review-gauntlet review` SHALL return structured failed-cell output when any adapter invocation fails. Successful cells from the same run SHALL still persist coverage and findings before the command exits.

#### Scenario: Zero-cell review does not create run record

**Given**: an active session whose current cells are already reviewed
**When**: the developer runs `review-gauntlet review`
**Then**: no new reviewed-cell coverage is recorded
**And**: no run record is created

#### Scenario: Partial adapter failure preserves successful cells

**Given**: a review run with 3 pending cells
**And**: one adapter invocation fails
**When**: the run completes
**Then**: successful cells are recorded as reviewed
**And**: findings from successful cells are persisted
**And**: the failed cell remains pending for retry

### Requirement: Status and findings commands SHALL expose actionable session state

Status and findings commands SHALL reflect the simplified two-phase model. Finding state counts SHALL use `open`, `confirmed`, `dismissed`. Cell state counts SHALL use `pending`, `reviewed`. Stale-related state displays are removed.

#### Scenario: Status shows two-phase state

**Given**: an active session with 3 pending cells, 5 reviewed cells, 2 open findings, 1 confirmed finding
**When**: the developer runs `review-gauntlet status --format json`
**Then**: coverage shows `pending: 3`, `reviewed: 5`
**And**: findings show `open: 2`, `confirmed: 1`, `dismissed: 0`

### Requirement: Finalize SHALL validate completion without running review work

Finalize SHALL require all cells to be `REVIEWED` and all findings to be `confirmed` or `dismissed`. Finalize SHALL NOT require separate verification of fixed findings since the resolution agent handles verification as part of the `confirmed` determination.

#### Scenario: Successful finalize with two-phase completion

**Given**: an active review session with all cells `REVIEWED`
**And**: all findings are `confirmed` or `dismissed`
**And**: review-universe files are clean relative to `HEAD`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: `.review-gauntlet/checkpoints/latest/status.json` is written
**And**: stdout contains parseable JSON listing the generated files
**And**: the result includes `checkpoint_state: complete`

#### Scenario: Open findings block finalize

**Given**: an active review session with all cells reviewed
**And**: at least one finding is `open`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with structured blockers
**And**: blockers indicate open findings remain
**And**: no checkpoint files are written

## REMOVED Requirements

### Requirement: Fixed findings SHALL require later verification

Removed because the resolution agent handles both judgment and fix application in a single step. Finding `confirmed` is terminal and implies the fix is applied and verified by the agent.

### Requirement: Verify-fixes command SHALL re-review fixed findings explicitly

Removed because the `verify-fixes` command is removed. Verification is integrated into the resolution agent's `confirmed` determination.
