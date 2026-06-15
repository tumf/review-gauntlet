## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

`findings` SHALL cap emitted findings to 10 records by default after applying terminal visibility, path filters, and mark filters. `findings --limit N` SHALL cap emitted findings to the requested positive integer limit. `findings --all-findings` SHALL disable the result-size cap without changing terminal visibility. `findings --limit N --all-findings` SHALL fail with a usage error.

`findings` SHALL expose count metadata in both structured and text result payloads. `total` SHALL be the number of findings after terminal visibility, path, and mark filters but before result-size limiting. `returned` SHALL be the number of findings actually emitted. Findings SHALL be ordered deterministically by path, start line, end line, and finding ID before any result-size cap is applied.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. `status` SHALL report `coverage` as an effective read-only view of the active session's current target rather than a raw persisted review-cell count. Effective coverage SHALL be derived by comparing current target cells and current file digests against persisted review-cell rows without mutating the ledger. Current target cells missing from persisted rows SHALL count as `pending`. Current target cells whose persisted digest no longer matches the current digest SHALL count as `stale` only when their path has no live `fixed_pending_verification` findings. Persisted cells that are no longer part of the current target SHALL remain visible as `superseded` coverage when included in the effective coverage summary. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending, `status` SHALL expose review work as the next required action before exposing live finding work. When pending cells are exhausted but current review cells are stale, `status` SHALL expose live finding work before generic stale review work so fix-driven stale coverage can be handled after finding work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. When the last reviewed target digest differs from the current target digest, `status` SHALL NOT expose review work solely because of that whole-target digest drift if all current target cells are already present, reviewed, and have matching content digests, or if digest drift exists only on paths already represented by live `fixed_pending_verification` findings. In those cases, `status` SHALL continue normal finding-state priority, including fixed-finding verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending, `ready` SHALL prompt for pending review before prompting for reopened, untriaged, confirmed, fixed-pending, or stale work. When pending cells are exhausted but current review cells are stale, `ready` SHALL prompt for live finding work before prompting for generic stale review work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL NOT return a target-digest-drift review prompt solely because whole-target digest drift exists when current target-cell coverage is complete.

`review-gauntlet run` SHALL orchestrate an active session by repeatedly using the same continuation task prompt that `review-gauntlet ready` would emit. `run` SHALL NOT maintain independent task-selection priority logic. `run` SHALL invoke the configured command adapter as a session-level task runner with the ready prompt and then re-evaluate the active session. `run` SHALL NOT require the session-level agent invocation to emit OCR verdict JSON, and SHALL NOT use review-cell verdict parsing as the success criterion for a session-level task. `run` SHALL stop successfully when the active session has been finalized and the active-session marker is gone. `run` SHALL stop unsuccessfully when no ready task exists while a session remains active, when the configured command fails, when the configured maximum step count is reached while the session remains active, or when a user-requested stop after the current step leaves the session active. Interactive text executions of `review-gauntlet run` SHOULD use a Textual TUI by default when TUI support is installed, stdout is a TTY, `--format text` is selected, and `--no-tui` is not provided. `run --format json`, `run --no-tui`, and non-TTY executions SHALL NOT launch the TUI. TUI presentation SHALL NOT change task selection, command execution semantics, run result semantics, or session finalization semantics. TUI dependencies SHALL be optional; when TUI support is unavailable for an otherwise TUI-eligible run, the command SHALL warn and fall back to non-TUI text mode. When interrupted by the user, `run` SHALL NOT print a Python traceback. Instead, it SHALL return or emit a structured interrupted run result with `completed: false`, `reason: interrupted`, current step evidence when available, and the active session ID when available.

Interactive `run` TUI presentation SHALL prioritize current-target progress over generic application chrome. Its first visible dashboard area SHALL show percent complete, completed current cells over total current cells, elapsed time, current step, and session-level agent status. The progress denominator SHALL exclude `superseded` coverage. The incomplete count SHALL include current-target `pending` and `stale` coverage. Current-target cells in other coverage states SHALL count as complete for presentation purposes only; this presentation calculation SHALL NOT mutate or redefine durable coverage state. The TUI SHALL display coverage composition with compact graphical bars or equivalent dense visual text and SHALL keep pending and stale states visibly emphasized. The TUI SHALL display actionable finding-state counts from the run status payload, including payloads where counts are exposed as `finding_state_counts` rather than `findings`. While the run controller reports the session-level agent status as `running`, the TUI SHALL show visible activity animation such as a spinner or pulse indicator. When the agent is not running, the activity indicator SHALL stop or dim. The TUI SHALL remove default Textual header and footer chrome that would otherwise show a generic app title such as `RunApp` or a default left-side icon. These presentation requirements SHALL NOT change task selection, command execution, result payloads, interruption behavior, or fallback behavior.

#### Scenario: Run TUI shows current-target progress first

**Given**: an active session with effective coverage containing reviewed, pending, stale, and superseded cells
**And**: the `run` TUI is eligible for an interactive text execution
**When**: the TUI renders the session snapshot
**Then**: the first visible dashboard area shows the percent complete
**And**: it shows completed current cells over total current cells
**And**: it shows elapsed time, current step, and agent status
**And**: superseded cells are not included in the progress denominator

#### Scenario: Run TUI visualizes remaining work without hiding unknowns

**Given**: an active session with pending and stale effective coverage
**When**: the `run` TUI renders the coverage breakdown
**Then**: pending and stale counts are visually emphasized
**And**: coverage composition is represented with compact graphical bars or equivalent dense visual text
**And**: the TUI does not replace unknown or incomplete states with optimistic completion claims

#### Scenario: Run TUI displays finding counts from status payloads

**Given**: a run status snapshot whose finding counts are exposed as `finding_state_counts`
**When**: the `run` TUI renders finding-state details
**Then**: actionable finding counts are shown in the TUI
**And**: the TUI does not require a separate legacy `findings` key to display those counts

#### Scenario: Run TUI activity indicator follows agent status

**Given**: the run controller reports `agent_status` as `running`
**When**: the TUI refreshes while the session-level command is executing
**Then**: the visible status area includes an animated spinner or pulse indicator
**And**: when the run controller reports a non-running status, the running animation stops or becomes dim

#### Scenario: Run TUI omits generic Textual chrome

**Given**: an interactive TUI-eligible `review-gauntlet run`
**When**: the TUI is rendered
**Then**: the default Textual header title such as `RunApp` is not shown
**And**: the default header icon is not shown
**And**: keyboard controls remain available through a compact in-dashboard hint or equivalent non-header/footer presentation
