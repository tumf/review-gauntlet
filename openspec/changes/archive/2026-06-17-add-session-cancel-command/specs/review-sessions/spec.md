## ADDED Requirements

### Requirement: Cancel SHALL abandon the active review session without finalizing

`review-gauntlet cancel` SHALL provide an explicit way to abandon an active review session created by `init` without creating review execution evidence or finalization checkpoint artifacts. Cancellation SHALL be a durable session lifecycle transition to `cancelled`, not an implicit claim that review coverage or findings are complete.

#### Scenario: Cancel clears active session marker

**Given**: a repository with an active review session created by `review-gauntlet init`
**When**: the developer runs `review-gauntlet cancel --format json`
**Then**: stdout reports the cancelled `session_id`
**And**: stdout reports `session_state: cancelled`
**And**: `.review-gauntlet/active-session.json` no longer exists
**And**: the session ledger records the session state as `cancelled`

#### Scenario: Cancel does not create review or checkpoint evidence

**Given**: a repository with an active review session that has not been finalized
**When**: the developer runs `review-gauntlet cancel`
**Then**: no review run row is created by cancellation
**And**: no latest checkpoint files are written or updated by cancellation
**And**: review cells and findings are not marked reviewed, verified, waived, or finalized solely because the session was cancelled

#### Scenario: Cancelled session cannot be continued as active

**Given**: a repository whose active review session was cancelled successfully
**When**: the developer runs `review-gauntlet status`, `review-gauntlet ready`, or `review-gauntlet review` without running a new `init`
**Then**: the command fails with actionable no-active-session guidance
**And**: the cancelled session is not silently resumed
**And**: a subsequent `review-gauntlet init` creates a new active session ID

#### Scenario: Cancel requires an active session

**Given**: a repository without `.review-gauntlet/active-session.json`
**When**: the developer runs `review-gauntlet cancel`
**Then**: the command fails with actionable no-active-session guidance
**And**: it does not create a new review session, review run, or checkpoint artifact

#### Scenario: Cancel is documented as distinct from finalize

**Given**: a developer reads the review lifecycle documentation
**When**: they need to abandon an accidental `init`
**Then**: the documentation identifies `review-gauntlet cancel` as the supported command
**And**: the documentation distinguishes cancellation from `finalize` by stating that cancellation does not write a review checkpoint
