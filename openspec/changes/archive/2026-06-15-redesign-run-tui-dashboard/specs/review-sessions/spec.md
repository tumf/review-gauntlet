## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

`findings` SHALL cap emitted findings to 10 records by default after applying terminal visibility, path filters, and mark filters. `findings --limit N` SHALL cap emitted findings to the requested positive integer limit. `findings --all-findings` SHALL disable the result-size cap without changing terminal visibility. `findings --limit N --all-findings` SHALL fail with a usage error.

`findings` SHALL expose count metadata in both structured and text result payloads. `total` SHALL be the number of findings after terminal visibility, path, and mark filters but before result-size limiting. `returned` SHALL be the number of findings actually emitted. Findings SHALL be ordered deterministically by path, start line, end line, and finding ID before any result-size cap is applied.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. `status` SHALL report `coverage` as an effective read-only view of the active session's current target rather than a raw persisted review-cell count. Effective coverage SHALL be derived by comparing current target cells and current file digests against persisted review-cell rows without mutating the ledger. Current target cells missing from persisted rows SHALL count as `pending`. Current target cells whose persisted digest no longer matches the current digest SHALL count as `stale` only when their path has no live `fixed_pending_verification` findings. Persisted cells that are no longer part of the current target SHALL remain visible as `superseded` coverage when included in the effective coverage summary. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending, `status` SHALL expose review work as the next required action before exposing live finding work. When pending cells are exhausted but current review cells are stale, `status` SHALL expose live finding work before generic stale review work so fix-driven stale coverage can be handled after finding work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. When the last reviewed target digest differs from the current target digest, `status` SHALL NOT expose review work solely because of that whole-target digest drift if all current target cells are already present, reviewed, and have matching content digests, or if digest drift exists only on paths already represented by live `fixed_pending_verification` findings. In those cases, `status` SHALL continue normal finding-state priority, including fixed-finding verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending, `ready` SHALL prompt for pending review before prompting for reopened, untriaged, confirmed, fixed-pending, or stale work. When pending cells are exhausted but current review cells are stale, `ready` SHALL prompt for live finding work before prompting for generic stale review work. Live finding work SHALL include reopened findings, untriaged findings, confirmed findings, and fixed-pending verification. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL NOT return a target-digest-drift review prompt solely because whole-target digest drift exists when current target-cell coverage is complete.

`review-gauntlet run` SHALL orchestrate an active session by repeatedly using the same continuation task prompt that `review-gauntlet ready` would emit. `run` SHALL NOT maintain independent task-selection priority logic. `run` SHALL invoke the configured command adapter as a session-level task runner with the ready prompt and then re-evaluate the active session. `run` SHALL NOT require the session-level agent invocation to emit OCR verdict JSON, and SHALL NOT use review-cell verdict parsing as the success criterion for a session-level task. `run` SHALL stop successfully when the active session has been finalized and the active-session marker is gone. `run` SHALL stop unsuccessfully when no ready task exists while a session remains active, when the configured command fails, when the configured maximum step count is reached while the session remains active, or when a user-requested stop after the current step leaves the session active. Interactive text executions of `review-gauntlet run` SHOULD use a Textual TUI by default when TUI support is installed, stdout is a TTY, `--format text` is selected, and `--no-tui` is not provided. `run --format json`, `run --no-tui`, and non-TTY executions SHALL NOT launch the TUI. TUI presentation SHALL NOT change task selection, command execution semantics, run result semantics, or session finalization semantics. TUI dependencies SHALL be optional; when TUI support is unavailable for an otherwise TUI-eligible run, the command SHALL warn and fall back to non-TUI text mode. When interrupted by the user, `run` SHALL NOT print a Python traceback. Instead, it SHALL return or emit a structured interrupted run result with `completed: false`, `reason: interrupted`, current step evidence when available, and the active session ID when available.

Interactive `run` TUI presentation SHALL use Textual as the interactive TTY dashboard framework. Rich renderables MAY be used inside Textual widgets, but the TUI SHALL be structured as an application dashboard rather than raw Rich panels arranged as a log display. The TUI SHALL derive a human-facing run view model from raw controller state before rendering. The view model SHALL include status, shortened session ID, agent or command display name, step label, elapsed time, coverage metrics, finding metrics, current task title and description, command label, and human-readable timeline events. Widgets SHALL render this view model rather than directly dumping raw prompt text, raw argv payloads, raw event payloads, or raw session IDs.

Interactive `run` TUI presentation SHALL prioritize current-target progress over generic application chrome. Its first visible dashboard area SHALL show percent complete, completed cells over total cells, elapsed time, current step, session-level agent status, and shortened session ID. The progress denominator SHALL exclude `superseded` coverage. The incomplete count SHALL include current-target `pending` and `stale` coverage. Current-target cells in other coverage states SHALL count as complete for presentation purposes only; this presentation calculation SHALL NOT mutate or redefine durable coverage state. The TUI SHALL display coverage composition with compact graphical bars or equivalent dense visual text and SHALL keep pending and stale states visibly emphasized without rendering error-like markers such as `! pending` or `! stale`. The TUI SHALL display actionable finding-state counts from the run status payload, including payloads where counts are exposed as `finding_state_counts` rather than `findings`. Findings SHALL remain visible even when all finding counts are zero. While the run controller reports the session-level agent status as `running`, the TUI SHALL show visible activity animation such as a spinner or pulse indicator. When the agent is not running, the activity indicator SHALL stop or dim. The TUI SHALL remove default Textual header and footer chrome that would otherwise show a generic app title such as `RunApp` or a default left-side icon. Keyboard controls SHALL remain available through a compact in-dashboard hint that lists only implemented controls. These presentation requirements SHALL NOT change task selection, command execution, result payloads, interruption behavior, or fallback behavior.

Interactive `run` TUI presentation SHALL use semantic state colors. Normal panel borders SHALL use muted blue or gray styling, not yellow. Yellow SHALL be reserved for pending work, blockers, human-action-needed states, or warnings. Failed states SHALL use red semantic styling, finalized states SHALL use green semantic styling, and active/running task focus MAY use blue or green styling. Blocked, failed, and finalized states SHALL have distinct human-readable summary text describing the current condition and next action or evidence path when available.

Interactive `run` TUI activity presentation SHALL render human-readable timeline rows instead of raw event logs. Timeline timestamps SHALL be displayed as `HH:MM:SS`. Timeline labels SHALL describe events such as run start, status refresh, step start, agent start, agent finish, blocked, failed, and finalized. Timeline details SHALL shorten session IDs, summarize prompt intent through task titles, omit empty argv values, and avoid displaying `argv=[]`, `command n/a`, raw full prompts, or ISO timestamps. Malformed event timestamps or unexpected payloads SHALL NOT crash TUI rendering.

Interactive `run` TUI current operation presentation SHALL render ready prompts as human task titles and descriptions rather than displaying the full prompt as the primary text. At minimum, pending review, stale review, untriaged finding triage, confirmed finding fix, fixed-pending verification, and finalization prompts SHALL map to stable task titles. Unknown prompt text SHALL be sanitized and summarized without dumping the full internal instruction body.

Interactive `run` TUI presentation SHALL include a compact layout suitable for approximately 80x24 terminals. In compact layout, Coverage and Findings MAY stack vertically and labels MAY be shortened, but status, coverage progress, pending/stale visibility, finding counts, current task, recent activity, and implemented controls SHALL remain readable.

<!-- Expected canonical result after archive: the canonical review-sessions spec will define the run TUI as a Textual dashboard driven by a human-facing view model, with semantic colors, stable coverage/findings metrics, prompt-to-task presentation, readable timelines, terminal-state summaries, and compact layout behavior while preserving run semantics. -->

#### Scenario: Run TUI renders a Textual dashboard from a view model

**Given**: an active review session with a configured command adapter and effective coverage/finding status
**And**: the `run` TUI is eligible for an interactive text execution
**When**: the TUI renders the session snapshot
**Then**: the TUI uses Textual dashboard regions for header, metrics, current operation, activity, and controls
**And**: the rendered widgets use human-facing view model fields rather than raw controller payload dumps
**And**: task selection, command execution, result payloads, interruption behavior, and fallback behavior remain unchanged

#### Scenario: Run TUI shows dashboard coverage and findings metrics

**Given**: an active session with effective coverage containing reviewed, pending, stale, and superseded cells
**And**: finding counts for open, untriaged, confirmed, reopened, fixed-pending, and closed findings
**When**: the `run` TUI renders the metrics dashboard
**Then**: Coverage shows percent complete, a progress bar or equivalent dense indicator, reviewed cells over total cells, and reviewed, pending, stale, and superseded counts
**And**: the progress denominator excludes superseded cells
**And**: Findings remains visible even when every finding count is zero
**And**: the coverage text does not use `current cells`, `! pending`, or `! stale`

#### Scenario: Run TUI renders human-readable current operation

**Given**: `review-gauntlet ready` returns a prompt for pending review, stale review, finding triage, confirmed finding fix, fixed-pending verification, or finalization
**When**: the `run` TUI renders the current operation panel
**Then**: the TUI displays a stable human task title and short description for that prompt intent
**And**: the full internal prompt is not displayed as the primary task text
**And**: unresolved command state does not render `command n/a`

#### Scenario: Run TUI renders human-readable activity timeline

**Given**: the run controller has emitted events containing ISO timestamps, session IDs, prompt payloads, or argv payloads
**When**: the `run` TUI renders the activity timeline
**Then**: each visible event row uses `HH:MM:SS` timestamp formatting
**And**: event labels are human-readable
**And**: session IDs are shortened
**And**: empty argv values are omitted
**And**: the timeline does not display `argv=[]`, raw full prompts, or raw ISO timestamps

#### Scenario: Run TUI distinguishes terminal states semantically

**Given**: a run is blocked, failed, or finalized
**When**: the `run` TUI renders the dashboard
**Then**: blocked state uses warning styling and explains the blocker or next action
**And**: failed state uses failure styling and points to available command failure evidence
**And**: finalized state uses success styling and summarizes completed coverage and open findings
**And**: normal non-terminal panel borders do not use warning styling

#### Scenario: Run TUI remains readable in compact terminals

**Given**: the terminal is approximately 80 columns by 24 rows
**When**: the `run` TUI renders the dashboard
**Then**: the layout remains readable without losing status, coverage progress, pending/stale counts, finding counts, current task, recent activity, or implemented controls
**And**: Coverage and Findings may stack vertically if horizontal metric cards would not fit
