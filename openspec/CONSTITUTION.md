# Constitution of review-gauntlet

## Overview

review-gauntlet is software that manages not only the results of AI code review, but also **what has been reviewed and what has not yet been reviewed**.

---

## Principles

### 1. Coverage is a product

Review coverage is not a byproduct.
It is a first-class output of review-gauntlet.

### 2. Reviewed means executed, not safe

`reviewed` does not mean "is safe."
`reviewed` means only that the defined target was reviewed with the defined rule, in a verifiable form.

### 3. The system records coverage

Reviewed scope must not be determined by the LLM's self-reporting.
The system records it based on file, rule, slice, prompt, model, and code digest.

### 4. Unknown must stay visible

Unreviewed, failed, stale, and needs-retry states must not be hidden.
Incompleteness is part of the output.

### 5. One review command advances once

`review-gauntlet review` advances the session by exactly one step.
It must not auto-loop until completion.

### 6. Orchestration is external

Developer notification, fix-waiting, retry loops, and CI control are external concerns.
review-gauntlet provides state and verdicts.

### 7. Findings are stateful

Every finding is assigned a stable ID.
A re-detected issue must not be treated as a separate new finding.

### 8. Human decisions are ledger entries

Decisions such as fixed, waived, false positive, and accepted risk must be recorded in a ledger.
The reason, actor, and timestamp of the decision must never be lost.

### 9. Fixed is not final until verified

Fixed is not immediately terminal.
It must be marked `fixed_pending_verification` until validated in a subsequent review.

### 10. Completion requires two closures

Session completion requires both of the following:
- The current review coverage is in a terminal state.
- All live findings are in a terminal state.

### 11. Changes invalidate truth

Changes to code, rule, prompt, or target diff may stale past coverage as needed.
Old review results must not be treated as the current truth.

### 12. Determinism before cleverness

Before making the LLM behave intelligently, implement target partitioning, ID generation, dedupe, coverage computation, and state transitions deterministically.

### 13. Be explicit, not optimistic

review-gauntlet must never claim "we've probably seen everything."
Always be explicit about: reviewed scope, unreviewed scope, decided items, and undecided items.
