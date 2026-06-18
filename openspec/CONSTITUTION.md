# Constitution of review-gauntlet

## Overview

review-gauntlet is software that manages not only the results of AI code review, but also **what has been reviewed and what has not yet been reviewed**.

---

## Principles

### Coverage is a product

Review coverage is not a byproduct.
It is a first-class output of review-gauntlet.

### The system records coverage

Reviewed scope must not be determined by the LLM's self-reporting.
The system records it based on file, rule, slice, prompt, model, and code digest.

### Unknown must stay visible

Unreviewed, failed, open, and needs-retry states must not be hidden.
Incompleteness is part of the output.

### One review command advances one phase

`review-gauntlet review` advances the session by exactly one review phase.
It must not run the resolve phase or finalize the session.

### Orchestration is external

Developer notification, fix-waiting, retry loops, and CI control are external concerns.
review-gauntlet provides state and verdicts.

### Findings are stateful

Every finding is assigned a stable ID.
A re-detected issue must not be treated as a separate new finding.

### Human decisions are ledger entries

Decisions such as fixed, waived, false positive, and accepted risk must be recorded in a ledger.
The reason, actor, and timestamp of the decision must never be lost.

### Resolution records judgment and action together

Finding resolution must record whether each open finding was confirmed or dismissed.
Confirmed findings are fixed in the same resolve phase; dismissed findings require a durable reason.

### Completion requires two closures

Session completion requires both of the following:
- The current review coverage is in a terminal state.
- All live findings are in a terminal state.

### Review truth is deterministic per session

Review truth is scoped to the deterministic target, rule, prompt, and code digest recorded for the session.
Old review results must not be treated as current truth outside that recorded session context.

### Determinism before cleverness

Before making the LLM behave intelligently, implement target partitioning, ID generation, dedupe, coverage computation, and state transitions deterministically.

### Be explicit, not optimistic

review-gauntlet must never claim "we've probably seen everything."
Always be explicit about: reviewed scope, unreviewed scope, decided items, and undecided items.

### Best-effort completion over early abort

When an error occurs during a review session, the system must continue processing remaining targets rather than aborting the entire session.
Individual failures are recorded as failed status on the affected target; unaffected targets must still be reviewed.

### Bounded progress, no infinite loops

Every loop in the orchestration must have an explicit upper bound (e.g., max retries, max phases, max iterations).
If progress stalls — no state transition after a bounded number of attempts — the system must halt with a clear diagnostic rather than retry indefinitely.
