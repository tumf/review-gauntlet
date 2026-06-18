# Constitution of review-gauntlet

## Overview

review-gauntlet is software that manages not only the results of AI code review, but also **what has been reviewed and what has not yet been reviewed**.

---

## Principles

### Coverage is a product

Review coverage is not a byproduct.
It is a first-class output of review-gauntlet.

### The system tracks coverage

Reviewed scope should not rely only on the LLM's self-reporting.
The system keeps enough structured state to show which targets were reviewed and which remain.

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

Findings should have stable enough identity to avoid reporting the same issue as new on every pass.
The system should favor continuity over perfect provenance.

### Human decisions are lightweight state

Decisions such as fixed, waived, false positive, and accepted risk should be recorded simply enough to resume work later.
The system should preserve the decision and a short reason without turning normal review into audit bureaucracy.

### Resolution records outcome and next step

Finding resolution should record whether each open finding was confirmed or dismissed.
Confirmed findings should lead to a fix attempt; dismissed findings should include a short reason.

### Completion requires two closures

Session completion requires both of the following:
- The current review coverage is in a terminal state.
- All live findings are in a terminal state.

### Review truth is scoped to the session

Review results are valid for the session inputs they were produced from.
Old results should not be treated as current after the target or review intent changes.

### Determinism before cleverness

Before making the LLM behave intelligently, implement target partitioning, dedupe, coverage computation, and state transitions predictably.

### Be explicit, not optimistic

review-gauntlet must never claim "we've probably seen everything."
Always be explicit about: reviewed scope, unreviewed scope, decided items, and undecided items.

### Best-effort completion over early abort

When an error occurs during a review session, the system must continue processing remaining targets rather than aborting the entire session.
Individual failures are recorded as failed status on the affected target; unaffected targets must still be reviewed.

### Bounded progress, no infinite loops

Every loop in the orchestration must have an explicit upper bound (e.g., max retries, max phases, max iterations).
If progress stalls — no state transition after a bounded number of attempts — the system must halt with a clear diagnostic rather than retry indefinitely.
