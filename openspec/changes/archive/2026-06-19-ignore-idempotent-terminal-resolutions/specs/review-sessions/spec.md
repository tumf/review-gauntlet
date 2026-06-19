## MODIFIED Requirements

### Requirement: Finding triage SHALL be explicit and event-backed

Finding triage SHALL transition findings from `open` to either `confirmed` (real finding handled by the resolution phase) or `dismissed` (not a valid issue or intentionally closed as a non-issue). Triage event metadata SHALL be validated before persistence. Dismissed findings SHALL include a `dismiss_reason`. Both `confirmed` and `dismissed` are terminal states.

Resolve-phase ready prompts SHALL describe the allowed transition targets for the current finding state before asking an external agent to write a resolution verdict. For `open` findings, the prompt SHALL instruct agents to use only `confirmed` or `dismissed`, and SHALL explain that false positives and other non-issues are represented as `dismissed` with a durable reason.

Turn verdict validation SHALL reject invalid requested finding transitions before persistence and SHALL report the finding ID, current state, requested state, and allowed target states. Turn verdict validation SHALL distinguish invalid transitions from stale idempotent terminal no-ops. When a verdict requests the same state already held by a terminal finding, the system SHALL treat that resolution as an ignored no-op rather than a failed transition, while preserving structured evidence that the stale resolution was ignored. A verdict SHALL NOT change a terminal finding to a different terminal or non-terminal state through this no-op handling.

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

#### Scenario: Idempotent terminal resolution is ignored with evidence

**Given**: an active session with finding `RGF-1021` already in terminal state `dismissed`
**And**: a turn verdict requests state `dismissed` for `RGF-1021`
**When**: Review Gauntlet validates and applies the turn verdict against the active session
**Then**: validation does not fail because of `RGF-1021`
**And**: no additional state transition is persisted for `RGF-1021`
**And**: structured output, run metadata, or continuation metadata identifies `RGF-1021` as an ignored idempotent terminal resolution

#### Scenario: Terminal semantic change remains invalid

**Given**: an active session with finding `RGF-1022` already in terminal state `false_positive`
**And**: a turn verdict requests state `dismissed` for `RGF-1022`
**When**: Review Gauntlet validates the turn verdict against the active session
**Then**: validation fails before the finding state is persisted
**And**: the diagnostic names `RGF-1022`, `false_positive`, and `dismissed`
**And**: the diagnostic explains that the current terminal state cannot transition to a different requested state

#### Scenario: Mixed valid and idempotent terminal resolutions preserve valid progress

**Given**: an active session with finding `RGF-1023` in state `open`
**And**: the same active session has finding `RGF-1024` already in terminal state `dismissed`
**And**: a turn verdict requests `dismissed` for both findings
**When**: Review Gauntlet applies the turn verdict against the active session
**Then**: `RGF-1023` transitions from `open` to `dismissed`
**And**: `RGF-1024` remains `dismissed` without an additional transition event
**And**: the applied verdict evidence identifies `RGF-1024` as an ignored idempotent terminal resolution
