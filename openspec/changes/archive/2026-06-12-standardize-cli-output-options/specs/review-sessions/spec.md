## MODIFIED Requirements

### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`. Review universe construction SHALL apply deterministic built-in artifact exclusions and default review-path exclusions, including `openspec/`, `tests/`, and `docs/`, before creating review cells. Review cell ledger identity SHALL be scoped to the owning session, so multiple sessions MAY contain the same deterministic review cell ID without corrupting or blocking each other. `init` SHALL support `--format text|json`, defaulting to `text`, and SHALL NOT expose `--audience` because it only emits a final initialization result.

<!-- Expected canonical result after archive: init documents `--format text|json`, default `text`, and rejection of non-progress audience options. -->

#### Scenario: Initialize a second session with overlapping review cells

**Given**: a repository with an existing `.review-gauntlet/` ledger from a prior `review-gauntlet init`
**And**: the next requested target includes one or more files that produce the same deterministic review cell IDs as the prior session
**When**: the developer runs `review-gauntlet init --all --format json`
**Then**: the CLI creates a new durable session
**And**: records review cells for the new session without failing on duplicate deterministic `cell_id` values from the prior session
**And**: keeps coverage and cell state scoped to each session
**And**: stdout contains parseable JSON for the final initialization result

#### Scenario: Init rejects obsolete output controls

**Given**: a repository root
**When**: the developer runs `review-gauntlet init --format human`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet init --audience agent`
**Then**: the command fails with a usage error

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

The review command SHALL support a positive integer `--concurrency` option, defaulting to `8`, that limits how many selected review cells may execute adapter review work simultaneously within that one run. The concurrency option SHALL NOT change the review budget, selected-cell eligibility, target policy, or the requirement that coverage is recorded only for successfully executed cells.

The review command SHALL support `--format text|json`, defaulting to `text`. For default human-audience runs, the review command SHALL expose review-run and per-cell progress on stderr while adapter work is in progress. Progress output SHALL NOT pollute stdout final output. When `--audience agent` is explicitly selected, the review command SHALL suppress decorative progress because agent callers do not need progress display. If the user interrupts the command, the review command SHALL cancel pending work, terminate in-flight command adapter subprocesses when possible, and leave unfinished cells in a non-reviewed state.

<!-- Expected canonical result after archive: review documents `--format text|json`, default `text`, keeps `--audience human|agent`, and rejects `--format human`. -->

#### Scenario: Human review reports progress without corrupting final output

**Given**: an active session with selected review cells
**When**: the developer runs `review-gauntlet review --format json`
**Then**: the CLI writes run and per-cell progress to stderr while adapter work is in progress
**And**: stdout remains exactly one parseable final JSON result
**And**: the progress includes the run id, selected cell count, concurrency, adapter identity when available, and cell start/completion or failure events

#### Scenario: Agent audience suppresses decorative review progress

**Given**: an active session with selected review cells
**When**: automation runs `review-gauntlet review --format json --audience agent`
**Then**: stdout contains only the final parseable JSON result
**And**: decorative progress text is not emitted for the agent audience

#### Scenario: Review rejects obsolete human format option

**Given**: an active session
**When**: the developer runs `review-gauntlet review --format human`
**Then**: the command fails with a usage error

### Requirement: Finding triage SHALL be explicit and event-backed

The CLI SHALL provide a `mark` command that records human or external-LLM triage decisions as events and updates the current finding state without executing review work. `mark` SHALL support `--format text|json`, defaulting to `text`, and SHALL NOT expose `--audience` because it only emits a final triage result.

<!-- Expected canonical result after archive: mark documents `--format text|json`, default `text`, and rejection of non-progress audience options. -->

#### Scenario: Mark finding false positive

**Given**: an active session with an open finding
**When**: the developer runs `review-gauntlet mark RGF-123 false-positive --reason "Protected by middleware" --format json`
**Then**: the CLI records a finding event with the reason
**And**: updates the finding status to `false_positive`
**And**: does not create a review run
**And**: stdout contains parseable JSON for the final mark result

#### Scenario: Mark rejects obsolete output controls

**Given**: an active session with an open finding
**When**: the developer runs `review-gauntlet mark RGF-123 fixed --format human`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet mark RGF-123 fixed --audience agent`
**Then**: the command fails with a usage error

### Requirement: Status and findings commands SHALL expose actionable session state

The CLI SHALL expose current session state without modifying review coverage. `status` SHALL report coverage, finding counts, target freshness, finalization readiness, and the next required action. `findings` SHALL list open findings by default and support showing all findings.

Session commands that emit summaries SHALL use `--format text` for human-readable output and `--format json` for structured output where supported, with `text` as the default. Commands that support decorative progress or audience-specific progress output SHALL support `--audience human|agent` for progress control. Commands that only emit a final result and no intermediate progress UI SHALL NOT expose an `--audience` option.

<!-- Expected canonical result after archive: status and findings use `--format text|json`, default `text`; findings continues to reject `--audience`; non-progress summary commands are not described as needing audience controls. -->

#### Scenario: Status reports next action

**Given**: an active session with reviewed cells and untriaged findings
**When**: the developer runs `review-gauntlet status --format json`
**Then**: the JSON output includes `session_id`, `session_state`, coverage counts, finding state counts, `can_finalize`, and `next_required_action`
**And**: `next_required_action` is `triage_findings`

#### Scenario: Non-progress status rejects audience option

**Given**: an active session
**When**: the developer runs `review-gauntlet status --audience agent`
**Then**: the command fails with a usage error

#### Scenario: Status rejects obsolete human format option

**Given**: an active session
**When**: the developer runs `review-gauntlet status --format human`
**Then**: the command fails with a usage error

#### Scenario: Findings hides terminal findings by default

**Given**: an active session with open and terminal findings
**When**: the developer runs `review-gauntlet findings`
**Then**: the output includes open findings
**And**: terminal findings are omitted unless `--all` is provided

#### Scenario: Findings uses text output by default

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --help`
**Then**: the help output lists `--format {text,json}`
**And**: the help output does not list `--audience`

#### Scenario: Findings emits structured JSON on request

**Given**: an active session with findings
**When**: the developer runs `review-gauntlet findings --format json`
**Then**: stdout contains parseable JSON for the final findings result

#### Scenario: Findings rejects obsolete audience and human format options

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --audience agent`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet findings --format human`
**Then**: the command fails with a usage error

### Requirement: Finalize SHALL validate completion without running review work

`review-gauntlet finalize` SHALL determine whether the active session can be completed. It SHALL not execute review work, triage findings, or modify source code. If completion conditions are unmet, it SHALL fail with actionable reasons. `finalize` SHALL support `--format text|json` for final output, defaulting to `text`, and SHALL NOT expose `--audience` because it does not emit progress UI.

<!-- Expected canonical result after archive: finalize documents `--format text|json`, default `text`, and rejection of non-progress audience options. -->

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
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the session is finalized
**And**: the command reports final coverage and finding totals as parseable JSON

#### Scenario: Finalize rejects obsolete output controls

**Given**: an active session
**When**: the developer runs `review-gauntlet finalize --format human`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet finalize --audience agent`
**Then**: the command fails with a usage error

### Requirement: Existing planning commands SHALL remain compatible

The session workflow SHALL preserve the existing `inventory`, `plan`, and `report` command concepts while making planning command output selection explicit. `inventory`, `plan`, and `report` SHALL accept `--format json|text`, default to `text`, and SHALL no longer accept legacy output flags or obsolete format names. JSON output for `inventory --format json` and `plan --format json` SHALL remain parseable using the existing Pydantic JSON contracts. `report --format text` SHALL emit the existing Markdown-style review matrix report body. Inventory generation SHALL exclude review-gauntlet-generated session state, common cache/build/editor artifacts, and files ignored by Git when Git-backed discovery is available, so coverage reflects the project review target rather than generated tool state.

<!-- Expected canonical result after archive: planning command compatibility documents `--format json|text` for inventory/plan/report, default text output, removal of the legacy `--json` flag, and rejection of `report --format markdown` while retaining existing report text content. -->

#### Scenario: Existing inventory JSON remains parseable

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --format json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Existing plan JSON remains parseable

**Given**: a repository with files to classify into review slices
**When**: the developer runs `review-gauntlet plan <root> --format json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Inventory defaults to text output

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root>`
**Then**: stdout is deterministic human-readable text
**And**: stdout is not required to be parseable as JSON

#### Scenario: Plan defaults to text output

**Given**: a repository with files to classify into review slices
**When**: the developer runs `review-gauntlet plan <root>`
**Then**: stdout is deterministic human-readable text
**And**: stdout is not required to be parseable as JSON

#### Scenario: Legacy JSON flag is rejected for planning commands

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --json` or `review-gauntlet plan <root> --json`
**Then**: argument parsing fails with a usage error

#### Scenario: Existing report remains available as text

**Given**: a repository with files to review
**When**: the developer runs `review-gauntlet report <root>`
**Then**: the command emits the existing Markdown-style review matrix report as text
**And**: existing tests for report output continue to pass

#### Scenario: Report accepts text format and rejects markdown format name

**Given**: a repository with files to review
**When**: the developer runs `review-gauntlet report <root> --format text`
**Then**: the command emits the existing Markdown-style review matrix report as text
**When**: the developer runs `review-gauntlet report <root> --format markdown`
**Then**: argument parsing fails with a usage error
