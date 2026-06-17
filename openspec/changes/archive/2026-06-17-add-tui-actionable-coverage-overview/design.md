# Design: Actionable Coverage Overview

## Goal

The run TUI should compress a large review session into the same operational shape as a system monitor: high-level status, the most important next items, hot spots, and recent activity. The underlying review-cell matrix remains authoritative but should not be the overview layout.

## Current Architecture

- `SessionStore` persists `review_cells`, `findings`, `finding_occurrences`, runs, and session metadata in `.review-gauntlet/ledger.sqlite`.
- `cli._status()` currently returns aggregate coverage counts and finding state counts.
- `RunController.snapshot()` carries aggregate `coverage`, aggregate `findings`, finalization blockers, next action, and agent lifecycle into the TUI.
- `run_tui.py` builds `RunViewState` from `RunSnapshot` and renders header, finalize checklist, Agent, Session, and Activity panels.

## Coverage Display Model

The full file × rule coverage matrix is an internal data model. The overview screen shows actionable projections of that matrix:

- Next review queue
- Rule coverage summary
- File hotlist
- Open findings
- Recent activity

The primary overview question is:

> What is blocking finalization, and what should be reviewed next?

The TUI should avoid wide matrix layouts because both file count and rule count can exceed terminal dimensions.

Detailed matrix-like navigation is provided through focused views:

- Files view: select a file, show rule states for that file
- Rules view: select a rule, show file states for that rule
- Cells view: show all file × rule cells as a flat sortable/filterable table
- Findings view: show finding lifecycle and blockers
- Agent view: show live output, current prompt/task, retry/timeout/status context

The overview must remain useful at 80 columns. At narrow widths, it should prioritize:

1. session status
2. coverage summary
3. finalize blockers
4. next review queue
5. activity

## Projection Derivation

Projection derivation should be deterministic and preferably centralized outside low-level Textual widget code. Inputs should include:

- current review cells derived from the target plan and file digests
- persisted review-cell state and content digest
- live/actionable findings and their latest occurrences
- finalization blockers and next required action
- optional active agent cell/prompt metadata when available

Queue entries should represent flattened review cells with display-relevant metadata:

```text
cell_id
file_path
rule_id
slice_id
state
priority_label
priority_score
finding_count
actionable_finding_count
stale_reason
why
changed_since_review
```

Raw scores are internal. The UI displays only P0/P1/P2/P3 labels.

## Priority Model

Initial deterministic priority scoring:

```text
score = 0
if cell has actionable finding:
    score += 1000
if cell.status == "stale":
    score += 500
if cell.status == "pending":
    score += 200
if cell.rule_id in high_risk_rules:
    score += 100
if cell.file_path changed since review:
    score += 80
score += finding_count * 50
score += risk_weight
```

Recommended initial risk weights based on existing rule IDs:

```text
secret-handling: 120
path-safety: 110
process-exec: 100
data-validation: 80
cli-contract: 60
ci-reproducibility: 50
test-evidence: 40
docs-accuracy: 20
```

Priority labels:

- P0: finalize blocker, actionable finding, or stale high-risk cell
- P1: should review soon, pending high-risk cell, or changed file
- P2: normal pending
- P3: low-risk or already reviewed

Tie-breaking must be stable, for example by descending score and then `(file_path, rule_id, cell_id)`.

## Rendering Strategy

Overview sections:

```text
header
next review queue
rule coverage + file hotlist
findings + activity
footer controls
```

Responsive behavior:

```text
>= 140 cols:
  header
  queue
  rule coverage + file hotlist
  findings + activity

100 - 139 cols:
  header
  queue
  rule coverage
  file hotlist
  findings/activity compact

< 100 cols:
  header
  queue
  blockers
  activity
```

Cells view should be a flat table rather than a wide matrix:

```text
state     pri  rule             file                         finding
stale     P0   secret-handling  src/api/auth.py              1
pending   P1   data-validation  src/parser.ts                0
reviewed  P3   docs-accuracy    README.md                    0
```

A symbolic matrix viewport can be added later as an optional view, not as the default overview.

## Compatibility

This change should not alter:

- review-cell identity
- coverage state transitions
- finding lifecycle semantics
- finalization gates
- markdown report matrix output
- JSON/text output contracts unless explicitly extended by a future proposal
- command adapter or hook execution behavior

## Verification Strategy

Unit tests should cover projection derivation, priority scoring, filters, responsive render section selection, and view switching. Integration verification is the existing project check command, `make check`, to ensure CLI, typechecking, linting, and tests still pass.
