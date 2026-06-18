## MODIFIED Requirements

### Requirement: Finding triage SHALL be explicit and event-backed

Finding triage SHALL transition findings from `open` to either `confirmed` (real finding handled by the resolution phase) or `dismissed` (not a valid issue or intentionally closed as a non-issue). Triage event metadata SHALL be validated before persistence. Dismissed findings SHALL include a `dismiss_reason`. Both `confirmed` and `dismissed` are terminal states.

Resolve-phase ready prompts SHALL describe the allowed transition targets for the current finding state before asking an external agent to write a resolution verdict. For `open` findings, the prompt SHALL instruct agents to use only `confirmed` or `dismissed`, and SHALL explain that false positives and other non-issues are represented as `dismissed` with a durable reason.

Turn verdict validation SHALL reject invalid requested finding transitions before persistence and SHALL report the finding ID, current state, requested state, and allowed target states.

#### Scenario: Open finding prompt lists only valid resolution states

**Given**: an active session with an `open` finding
**When**: `review-gauntlet run` builds a resolve ready prompt for that finding
**Then**: the prompt lists `confirmed` and `dismissed` as the allowed target states
**And**: the prompt does not instruct the agent to mark the open finding directly as `false_positive`, `accepted_risk`, `waived`, `fixed_pending_verification`, or `fixed_verified`

#### Scenario: False positive open finding is represented as dismissed

**Given**: an active session with an `open` finding
**When**: the resolution agent determines the finding is a false positive
**Then**: the prompt instructs the agent to emit a `dismissed` resolution
**And**: the prompt requires a durable `dismiss_reason`

#### Scenario: Invalid transition verdict is actionable

**Given**: an active session with finding `RGF-1020` in state `open`
**And**: a turn verdict requests state `false_positive` for `RGF-1020`
**When**: Review Gauntlet validates the turn verdict against the active session
**Then**: validation fails before the finding state is persisted
**And**: the diagnostic names `RGF-1020`, `open`, `false_positive`, and the allowed target states `confirmed` and `dismissed`
