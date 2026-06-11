## ADDED Requirements

### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events.

#### Scenario: Initialize a branch review session

**Given**: a repository with a valid base reference and head reference
**When**: the developer runs `review-gauntlet init --from origin/main --to HEAD`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records the base reference, head reference, moving head mode, target kind, ruleset digest, and initial review cells
**And**: does not execute a review run

#### Scenario: Initialize a worktree review session

**Given**: a repository with uncommitted changes
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the CLI creates a worktree-targeted session
**And**: records enough target information for later review runs to detect changed worktree content

#### Scenario: Initialize a fixed commit review session

**Given**: a repository with a valid commit object
**When**: the developer runs `review-gauntlet init --commit abc123`
**Then**: the CLI creates a fixed-target session for that commit
**And**: later runs treat the target as immutable unless a new session is initialized

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe, reconcile existing ledger state, review eligible cells within the configured budget, update cell coverage, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop.

#### Scenario: Review advances once with remaining pending work

**Given**: an active session with more pending review cells than the current review budget
**When**: the developer runs `review-gauntlet review`
**Then**: the CLI creates exactly one immutable run record
**And**: reviews only the cells selected for that run
**And**: leaves remaining eligible cells pending
**And**: reports that the next required action is to run review again or triage findings, depending on the run result

#### Scenario: Review does not auto-triage or auto-fix

**Given**: a review run produces a new finding
**When**: `review-gauntlet review` completes
**Then**: the finding status is `untriaged`
**And**: the CLI does not mark the finding false-positive, waived, accepted-risk, confirmed, or fixed on behalf of the developer

### Requirement: Review cells SHALL model coverage independently from finding state

The CLI SHALL track review cells as review coverage units separate from finding triage state. A cell MAY be reviewed while the session remains incomplete because associated findings are not terminal.

#### Scenario: Reviewed cell with untriaged finding is not complete session

**Given**: a review cell has been reviewed and produced a finding
**When**: the finding remains `untriaged`
**Then**: the cell counts as reviewed for coverage
**But**: the session cannot finalize

#### Scenario: Changed target invalidates prior coverage

**Given**: an active moving-target session with previously reviewed cells
**When**: the target content changes before a later review run
**Then**: affected current cells are marked stale or superseded according to whether they remain in the current review universe
**And**: new current cells are added as pending when required

### Requirement: Findings SHALL use stable session-level identity

Findings SHALL be managed at the review-session level and SHALL use deterministic IDs based on stable fingerprints. Repeated occurrences of the same logical issue across review runs SHALL attach to the existing finding instead of creating duplicate new findings.

#### Scenario: Same issue appears in multiple runs

**Given**: a review run detects a missing authorization finding in a file
**And**: a later review run detects the same logical issue with shifted line numbers
**When**: the later finding output is reconciled
**Then**: the CLI reuses the existing finding ID
**And**: records a new occurrence for the later run
**And**: does not display the issue as a new finding

#### Scenario: Fingerprint avoids line-number-only identity

**Given**: code edits shift a finding location without changing the enclosing issue
**When**: the finding fingerprint is computed
**Then**: semantic inputs such as file path, rule id, issue kind, enclosing symbol, normalized code anchor, and normalized claim are used
**And**: line number alone is insufficient to create a distinct finding identity

### Requirement: Finding triage SHALL be explicit and event-backed

The CLI SHALL provide a `mark` command that records human or external-LLM triage decisions as events and updates the current finding state without executing review work.

#### Scenario: Mark finding false positive

**Given**: an active session with an open finding
**When**: the developer runs `review-gauntlet mark RGF-123 false-positive --reason "Protected by middleware"`
**Then**: the CLI records a finding event with the reason
**And**: updates the finding status to `false_positive`
**And**: does not create a review run

#### Scenario: Mark finding accepted risk with expiry

**Given**: an active session with an open finding
**When**: the developer runs `review-gauntlet mark RGF-123 accepted-risk --owner "@team-a" --until 2026-09-30`
**Then**: the CLI records the owner and expiry metadata
**And**: treats the finding as terminal only until the expiry date is reached

### Requirement: Fixed findings SHALL require later verification

Marking a finding fixed SHALL transition it to `fixed_pending_verification`. The finding SHALL become terminal only after a later review run verifies the fix, and SHALL reopen if the same issue is detected again.

#### Scenario: Mark fixed is not terminal

**Given**: an active session with a confirmed finding
**When**: the developer runs `review-gauntlet mark RGF-123 fixed --reason "Added guard"`
**Then**: the finding status becomes `fixed_pending_verification`
**And**: the session cannot finalize until a later review verifies the fix

#### Scenario: Later review verifies fix

**Given**: a finding is `fixed_pending_verification`
**When**: a later review run evaluates the relevant current target and does not detect the same finding fingerprint
**Then**: the finding status becomes `fixed_verified`
**And**: the finding is terminal

#### Scenario: Later review reopens unfixed issue

**Given**: a finding is `fixed_pending_verification`
**When**: a later review run detects the same finding fingerprint again
**Then**: the finding status becomes `reopened`
**And**: the session cannot finalize until the reopened finding reaches a terminal state

### Requirement: Status and findings commands SHALL expose actionable session state

The CLI SHALL expose current session state without modifying review coverage. `status` SHALL report coverage, finding counts, target freshness, finalization readiness, and the next required action. `findings` SHALL list open findings by default and support showing all findings.

#### Scenario: Status reports next action

**Given**: an active session with reviewed cells and untriaged findings
**When**: the developer runs `review-gauntlet status --json`
**Then**: the JSON output includes `session_id`, `session_state`, coverage counts, finding state counts, `can_finalize`, and `next_required_action`
**And**: `next_required_action` is `triage_findings`

#### Scenario: Findings hides terminal findings by default

**Given**: an active session with open and terminal findings
**When**: the developer runs `review-gauntlet findings`
**Then**: the output includes open findings
**And**: terminal findings are omitted unless `--all` is provided

### Requirement: Finalize SHALL validate completion without running review work

`review-gauntlet finalize` SHALL determine whether the active session can be completed. It SHALL not execute review work, triage findings, or modify source code. If completion conditions are unmet, it SHALL fail with actionable reasons.

#### Scenario: Finalize fails with pending cells

**Given**: an active session with pending review cells
**When**: the developer runs `review-gauntlet finalize`
**Then**: the command fails
**And**: reports that review cells are still pending
**And**: does not create a review run

#### Scenario: Finalize fails with unverified fixes

**Given**: an active session with a `fixed_pending_verification` finding
**When**: the developer runs `review-gauntlet finalize`
**Then**: the command fails
**And**: reports that fixed findings require verification

#### Scenario: Finalize succeeds when coverage and findings are terminal

**Given**: all current review cells are terminal
**And**: all live findings are terminal
**And**: no waiver or accepted-risk finding is expired
**And**: the current target digest matches the last reviewed target digest
**When**: the developer runs `review-gauntlet finalize`
**Then**: the session is finalized
**And**: the command reports final coverage and finding totals

### Requirement: Existing planning commands SHALL remain compatible

The new session workflow SHALL preserve the existing `inventory`, `plan`, and `report` command contracts while reusing their concepts for review-universe generation.

#### Scenario: Existing inventory JSON remains parseable

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Existing report remains available

**Given**: a repository with files to review
**When**: the developer runs `review-gauntlet report <root>`
**Then**: the command emits the markdown review matrix report
**And**: existing tests for report output continue to pass
