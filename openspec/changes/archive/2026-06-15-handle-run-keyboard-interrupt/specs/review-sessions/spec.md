## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

`findings` SHALL cap emitted findings to 10 records by default after applying terminal visibility, path filters, and mark filters. `findings --limit N` SHALL cap emitted findings to the requested positive integer limit. `findings --all-findings` SHALL disable the result-size cap without changing terminal visibility. `findings --limit N --all-findings` SHALL fail with a usage error.

`findings` SHALL expose count metadata in both structured and text result payloads. `total` SHALL be the number of findings after terminal visibility, path, and mark filters but before result-size limiting. `returned` SHALL be the number of findings actually emitted. Findings SHALL be ordered deterministically by path, start line, end line, and finding ID before any result-size cap is applied.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. `status` SHALL report `coverage` as an effective read-only view of the active session's current target rather than a raw persisted review-cell count. Effective coverage SHALL be derived by comparing current target cells and current file digests against persisted review-cell rows without mutating the ledger. Current target cells missing from persisted rows SHALL count as `pending`. Current target cells whose persisted digest no longer matches the current digest SHALL count as `stale` only when their path has no live `fixed_pending_verification` findings. Persisted cells that are no longer part of the current target SHALL remain visible as `superseded` coverage when included in the effective coverage summary. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending, `status` SHALL expose review work as the next required action before exposing live finding work. When pending cells are exhausted but current review cells are stale, `status` SHALL expose live finding work before generic stale review work so fix-driven stale coverage can be handled after finding work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. When the last reviewed target digest differs from the current target digest, `status` SHALL NOT expose review work solely because of that whole-target digest drift if all current target cells are already present, reviewed, and have matching content digests, or if digest drift exists only on paths already represented by live `fixed_pending_verification` findings. In those cases, `status` SHALL continue normal finding-state priority, including fixed-finding verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending, `ready` SHALL prompt for pending review before prompting for reopened, untriaged, confirmed, fixed-pending, or stale work. When pending cells are exhausted but current review cells are stale, `ready` SHALL prompt for live finding work before prompting for generic stale review work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL NOT return a target-digest-drift review prompt solely because whole-target digest drift exists when current target-cell coverage is complete.

`review-gauntlet run` SHALL orchestrate an active session by repeatedly using the same continuation task prompt that `review-gauntlet ready` would emit. `run` SHALL NOT maintain independent task-selection priority logic. `run` SHALL invoke the configured command adapter as a session-level task runner with the ready prompt and then re-evaluate the active session. `run` SHALL NOT require the session-level agent invocation to emit OCR verdict JSON, and SHALL NOT use review-cell verdict parsing as the success criterion for a session-level task. `run` SHALL stop successfully when the active session has been finalized and the active-session marker is gone. `run` SHALL stop unsuccessfully when no ready task exists while a session remains active, when the configured command fails, when the configured maximum step count is reached while the session remains active, or when a user-requested stop after the current step leaves the session active. Interactive text executions of `review-gauntlet run` SHOULD use a Textual TUI by default when TUI support is installed, stdout is a TTY, `--format text` is selected, and `--no-tui` is not provided. `run --format json`, `run --no-tui`, and non-TTY executions SHALL NOT launch the TUI. TUI presentation SHALL NOT change task selection, command execution semantics, run result semantics, or session finalization semantics. TUI dependencies SHALL be optional; when TUI support is unavailable for an otherwise TUI-eligible run, the command SHALL warn and fall back to non-TUI text mode. When interrupted by the user, `run` SHALL NOT print a Python traceback. Instead, it SHALL return or emit a structured interrupted run result with `completed: false`, `reason: interrupted`, current step evidence when available, and the active session ID when available.

#### Scenario: Run invokes the same prompt as ready

**Given**: an active session with pending review cells
**And**: the effective adapter config invokes a fake command that records its arguments
**When**: the developer runs `review-gauntlet run --max-steps 1 --format json`
**Then**: the fake command receives the same prompt text that `review-gauntlet ready` emits for that session state
**And**: task selection comes from the ready prompt computation rather than from separate run-specific priority logic

#### Scenario: Run completes after the agent finalizes the session

**Given**: an active session whose next ready task can finalize the session
**And**: the configured command performs the required finalization so `.review-gauntlet/active-session.json` is removed
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the command exits `0`
**And**: stdout contains structured output indicating the run completed
**And**: the active session marker no longer exists

#### Scenario: Run fails when no ready task exists

**Given**: an active session for which `review-gauntlet ready` would emit no ready task and exit `1`
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the command exits `1`
**And**: stdout contains structured output identifying that no ready task is available
**And**: no agent command is invoked

#### Scenario: Run fails when the configured command fails

**Given**: an active session with a ready task
**And**: the effective adapter config invokes a command that exits non-zero or cannot be started
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the command exits `1`
**And**: stdout contains structured failure information
**And**: the active session remains available for later recovery

#### Scenario: Run enforces max steps

**Given**: an active session with a ready task
**And**: the configured command exits `0` without finalizing or otherwise removing the active session
**When**: the developer runs `review-gauntlet run --max-steps 1 --format json`
**Then**: the command exits `1`
**And**: stdout indicates the maximum step count was reached
**And**: the active session remains available for continuation

#### Scenario: Run does not parse session-level output as OCR verdict JSON

**Given**: an active session with a ready task
**And**: the configured command exits `0` while writing non-JSON progress text to stdout or stderr
**When**: the developer runs `review-gauntlet run --max-steps 1 --format json`
**Then**: the command does not fail solely because the session-level command output is not OCR verdict JSON
**And**: success or failure is determined by process exit status, max-step state, and active-session completion state

#### Scenario: Run launches TUI only for eligible interactive text executions

**Given**: an active session with a ready task
**And**: TUI support is installed
**And**: stdout is a TTY
**When**: the developer runs `review-gauntlet run`
**Then**: the command launches the Textual TUI presentation
**And**: the TUI uses the same run controller semantics as non-TUI run
**And**: TUI presentation changes only how state is displayed

#### Scenario: Run disables TUI for JSON output

**Given**: an active session with a ready task
**When**: the developer runs `review-gauntlet run --format json`
**Then**: no TUI is launched
**And**: stdout contains parseable JSON using the existing run result contract

#### Scenario: Run disables TUI when explicitly requested

**Given**: an active session with a ready task
**When**: the developer runs `review-gauntlet run --no-tui`
**Then**: no TUI is launched
**And**: text output uses the non-TUI run presentation

#### Scenario: Run disables TUI for non-TTY output

**Given**: an active session with a ready task
**And**: stdout is not a TTY
**When**: the developer runs `review-gauntlet run`
**Then**: no TUI is launched
**And**: output remains suitable for redirected logs or shell pipelines

#### Scenario: Run falls back when TUI dependency is missing

**Given**: TUI support is not installed
**And**: stdout is a TTY
**When**: the developer runs `review-gauntlet run`
**Then**: the command does not fail solely because Textual is missing
**And**: it emits a warning explaining how to install `review-gauntlet[tui]`
**And**: it continues with non-TUI text mode

#### Scenario: TUI stop request stops after current step

**Given**: the TUI run is executing a session-level agent step
**When**: the developer requests stop after current step
**Then**: the currently running step is allowed to finish
**And**: no additional ready prompt execution is started
**And**: the run exits unsuccessfully if the active session remains available for continuation

#### Scenario: TUI refresh does not mutate session state

**Given**: the TUI is displaying an active session
**When**: the developer requests refresh
**Then**: the TUI refreshes its display from durable session state through the run controller
**And**: no finding, review cell, or session state is mutated by the TUI itself

#### Scenario: Run handles user interrupt without traceback

**Given**: an active session with a ready task
**And**: the session-level command is running or about to run
**When**: the developer interrupts `review-gauntlet run` with Ctrl-C
**Then**: the command does not print a Python traceback
**And**: the run exits non-zero
**And**: the active session remains available for later continuation when it was not finalized

#### Scenario: Run emits structured JSON for user interrupt

**Given**: an active session with a ready task
**And**: the session-level command is interrupted by the user
**When**: the developer runs `review-gauntlet run --format json`
**Then**: stdout contains parseable JSON
**And**: the JSON result has `completed` equal to `false`
**And**: the JSON result has `reason` equal to `interrupted`
**And**: no traceback text is written as the user-facing result
