## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`review-gauntlet run` SHALL orchestrate an active session by repeatedly using the same continuation task prompt that `review-gauntlet ready` would emit. `run` SHALL NOT maintain independent task-selection priority logic. `run` SHALL invoke the configured command adapter as a session-level task runner with the ready prompt and then re-evaluate the active session. `run` SHALL NOT require the session-level agent invocation to emit OCR verdict JSON, and SHALL NOT use review-cell verdict parsing as the success criterion for a session-level task. `run` SHALL stop successfully when the active session has been finalized and the active-session marker is gone. `run` SHALL stop unsuccessfully when no ready task exists while a session remains active, when the configured command fails, when the configured maximum step count is reached while the session remains active, or when a user-requested stop after the current step leaves the session active. Interactive text executions of `review-gauntlet run` SHOULD use a Textual TUI by default when TUI support is installed, stdout is a TTY, `--format text` is selected, and `--no-tui` is not provided. `run --format json`, `run --no-tui`, and non-TTY executions SHALL NOT launch the TUI. TUI presentation SHALL NOT change task selection, command execution semantics, run result semantics, or session finalization semantics. TUI dependencies SHALL be optional; when TUI support is unavailable for an otherwise TUI-eligible run, the command SHALL warn and fall back to non-TUI text mode. When interrupted by the user, `run` SHALL NOT print a Python traceback. Instead, it SHALL return or emit a structured interrupted run result with `completed: false`, `reason: interrupted`, current step evidence when available, and the active session ID when available.

Interactive `run` TUI presentation SHALL use Textual as the interactive TTY dashboard framework. Rich renderables MAY be used inside Textual widgets, but the TUI SHALL be structured as an application dashboard rather than raw Rich panels arranged as a log display. The TUI SHALL derive a human-facing run view model from raw controller state before rendering. The view model SHALL include status, shortened session ID, agent or command display name, finalize gate label, agent step label, elapsed time, finalize-path gates, coverage metrics, finding metrics, blocker summaries, current operation title and description, command label, and human-readable timeline events. Widgets SHALL render this view model rather than directly dumping raw prompt text, raw argv payloads, raw event payloads, or raw session IDs.

Interactive `run` TUI presentation SHALL prioritize finalize progress over standalone coverage progress. Its primary visible dashboard area SHALL be a `Finalize path` panel with these ordered gates: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Resolve finalize blockers, and Finalize checkpoint. Each gate SHALL remain visible and SHALL render one of `active`, `done`, `waiting`, `blocked`, `skipped`, or `failed` plus a concise detail. The header SHALL prioritize `gate x/6` and the current gate title. Agent loop iterations SHALL be labeled as `agent step` and SHALL NOT be presented as the primary finalize progress indicator.

The TUI SHALL preserve coverage visibility as a session metric rather than the primary progress panel. Coverage presentation SHALL still show percent complete and reviewed cells over total cells; the progress denominator SHALL exclude `superseded` coverage. The incomplete count SHALL include current-target `pending` and `stale` coverage. Current-target cells in other coverage states SHALL count as complete for presentation purposes only; this presentation calculation SHALL NOT mutate or redefine durable coverage state. The TUI SHALL keep pending and stale states visibly emphasized without rendering error-like markers such as `! pending` or `! stale`. The TUI SHALL display actionable finding-state counts from the run status payload, including payloads where counts are exposed as `finding_state_counts` rather than `findings`. Finding triage, confirmed-fix, and fixed-verification gates SHALL remain visible even when all corresponding counts are zero. Resolve-blockers and finalize-checkpoint gates SHALL remain visible even when no blockers exist or finalization is not yet actionable. While the run controller reports the session-level agent status as `running`, the TUI SHALL show visible activity animation such as a spinner or pulse indicator. When the agent is not running, the activity indicator SHALL stop or dim. The TUI SHALL remove default Textual header and footer chrome that would otherwise show a generic app title such as `RunApp` or a default left-side icon. Keyboard controls SHALL remain available through a compact in-dashboard hint that lists only implemented controls.

Interactive `run` TUI presentation SHALL use semantic state colors. Normal panel borders SHALL use muted blue or gray styling, not yellow. Yellow SHALL be reserved for pending work, blockers, human-action-needed states, or warnings. Failed states SHALL use red semantic styling, finalized states SHALL use green semantic styling, and active/running gate focus MAY use blue or green styling. Blocked, failed, and finalized states SHALL have distinct human-readable summary text describing the current gate condition and next action or evidence path when available. A blocked run SHALL make the blocked gate obvious in the header and Finalize path panel. A finalized run SHALL render all gates complete and indicate that the checkpoint was written or the active session has disappeared after successful finalization.

Interactive `run` TUI activity presentation SHALL render human-readable timeline rows instead of raw event logs. Activity SHALL include both Review Gauntlet events and the bounded tail of agent stdout/stderr output. Timeline timestamps SHALL be displayed as `HH:MM:SS`. Timeline labels SHALL describe gate-centered events such as run start, gate active, agent step start, agent step finish, gate blocked, gate failed, and finalized. Agent output rows SHALL distinguish stdout from stderr. stderr output SHALL use warning-like presentation but SHALL NOT by itself mark the agent failed. Timeline details SHALL shorten session IDs, summarize prompt intent through gate or task titles, omit empty argv values, and avoid displaying `argv=[]`, `command n/a`, raw full prompts, or ISO timestamps. Malformed event timestamps or unexpected payloads SHALL NOT crash TUI rendering.

Interactive `run` TUI activity presentation SHALL bound and sanitize agent output. The TUI SHALL show a tail of recent output lines, defaulting to the latest 100 display lines. Older hidden output SHALL be indicated when lines are dropped from the display tail. A single displayed output line SHALL be truncated to a bounded display length, defaulting to 160 characters. Agent output SHALL be line-oriented; partial non-newline output MAY be flushed periodically, and repeated carriage-return progress updates MAY be represented by the latest observed state. The TUI SHALL strip ANSI escape sequences, broken escape fragments, bell/backspace/control characters, excessive blank lines, and other content that would corrupt the dashboard. The TUI SHALL redact common secret-looking assignments such as `*_TOKEN=...`, `*_SECRET=...`, and `*_KEY=...` in displayed output.

Session-level `run` agent execution SHALL persist complete agent output artifacts for audit and debugging. At minimum, each session-level agent step SHALL write full stdout, full stderr, and structured activity entries under a deterministic `.review-gauntlet/runs/<run-id>/` artifact directory or an equivalent tested run-step artifact directory. Activity displayed in the TUI is a tail summary and SHALL NOT be treated as the complete log. Initial implementation MAY persist raw output artifacts while applying redaction only to TUI display.

Interactive `run` TUI current operation presentation SHALL render ready prompts as human gate task titles and descriptions rather than displaying the full prompt as the primary text. At minimum, pending review, stale review, target-digest review, reopened finding triage, untriaged finding triage, confirmed finding fix, fixed-pending verification, blocker resolution, and finalization prompts SHALL map to stable task titles. Unknown prompt text SHALL be sanitized and summarized without dumping the full internal instruction body. Header or current-operation presentation SHALL also expose agent liveness using states such as `starting`, `running`, `quiet`, `finishing`, `completed`, `failed`, `timed_out`, or `cancelled`. While the agent process is active, the TUI SHALL show last-output age when recent output exists, quiet duration when no output has arrived for the quiet threshold, timeout remaining when known and approaching, and artifact path when available. Quiet process state SHALL be presented as alive/waiting, not as failure.

Interactive `run` TUI presentation SHALL include a compact layout suitable for approximately 80x24 terminals. In compact layout, secondary panels MAY stack vertically and labels MAY be shortened, and Review Gauntlet events plus agent output MAY be mixed chronologically rather than split into subsections. Run status, `gate x/6`, Finalize path gates, coverage progress, finding counts, blocker state, current operation, recent activity, recent agent output, and implemented controls SHALL remain readable.

Interactive `run` TUI presentation SHALL NOT automatically close when `RunController.run()` returns. Instead, once the controller finishes, the TUI SHALL retain the run result, render the terminal finalized/blocked/failed/stopped state, switch controls to explicit dismissal, and return the stored run result only after the user quits. While the controller is still active, `q` SHALL continue to request stop-after-current-step. After the controller has finished, `q` SHALL quit and return the stored result. Active-run `Ctrl-C` SHALL preserve interrupted-result behavior without a traceback; after the controller has finished, `Ctrl-C` MAY act as explicit dismissal of the final dashboard using the stored result. These presentation lifecycle requirements SHALL NOT change task selection, command execution, result payloads, interruption behavior, JSON output behavior, non-TUI behavior, or fallback behavior.

<!-- Expected canonical result after archive: the canonical review-sessions spec will define the run TUI as a Textual finalize-path dashboard driven by a human-facing view model, with six visible gates to checkpoint finalization, gate-first header/activity/current-operation presentation, coverage and findings retained as secondary session metrics, explicit post-completion dismissal, semantic terminal-state styling, compact layout behavior, and unchanged run semantics. -->

#### Scenario: Run TUI renders a finalize-path dashboard from a view model

**Given**: an active review session with a configured command adapter and effective coverage, finding, blocker, and finalize status
**And**: the `run` TUI is eligible for an interactive text execution
**When**: the TUI renders the session snapshot
**Then**: the TUI uses Textual dashboard regions for header, Finalize path, current operation, session metrics, activity, and controls
**And**: the Finalize path is the primary dashboard region
**And**: the rendered widgets use human-facing view model fields rather than raw controller payload dumps
**And**: task selection, command execution, result payloads, interruption behavior, and fallback behavior remain unchanged

#### Scenario: Run TUI shows finalize gate progress instead of coverage as primary progress

**Given**: an active session with effective coverage containing reviewed, pending, stale, and superseded cells
**And**: finding counts for open, untriaged, confirmed, reopened, fixed-pending, and closed findings
**When**: the `run` TUI renders the dashboard
**Then**: the header displays `gate x/6` and the current finalize gate title
**And**: the Finalize path panel shows Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Resolve finalize blockers, and Finalize checkpoint in order
**And**: each gate displays a state and concise detail
**And**: Coverage is rendered as a Session metrics item with percent complete and reviewed cells over total cells
**And**: Findings remains visible even when every finding count is zero
**And**: the coverage text does not use `current cells`, `! pending`, or `! stale`

#### Scenario: Run TUI separates finalize gates from agent loop steps

**Given**: the run controller is executing its second command-adapter invocation while the active finalize gate is Verify fixes
**When**: the `run` TUI renders the header and current operation
**Then**: the header prioritizes `gate 4/6 VERIFY FIXES`
**And**: the command-adapter invocation count is labeled `agent step 2`
**And**: the UI does not present bare `step 2` as the primary session progress label

#### Scenario: Run TUI renders human-readable current operation for finalize gates

**Given**: `review-gauntlet ready` returns a prompt for pending review, stale review, target-digest review, reopened finding triage, untriaged finding triage, confirmed finding fix, fixed-pending verification, blocker resolution, or finalization
**When**: the `run` TUI renders the current operation panel
**Then**: the TUI displays a stable human task title and short description for that gate intent
**And**: the full internal prompt is not displayed as the primary task text
**And**: unresolved command state does not render `command n/a`

#### Scenario: Run TUI renders gate-centered activity timeline with agent output

**Given**: the run controller has emitted events containing ISO timestamps, session IDs, prompt payloads, or argv payloads
**And**: the current agent step has emitted stdout and stderr lines
**When**: the `run` TUI renders the activity timeline
**Then**: each visible event row uses `HH:MM:SS` timestamp formatting
**And**: event labels are human-readable and gate-centered where possible
**And**: agent output rows distinguish `stdout` from `stderr`
**And**: session IDs are shortened
**And**: empty argv values are omitted
**And**: the timeline does not display `argv=[]`, raw full prompts, or raw ISO timestamps

#### Scenario: Run TUI bounds, sanitizes, and redacts agent output

**Given**: an agent emits more than the configured display-tail line count
**And**: output includes a very long line, ANSI/control characters, repeated blank lines, carriage-return progress, and `OPENAI_API_KEY=secret`
**When**: the `run` TUI renders agent output activity
**Then**: only the bounded recent tail is displayed
**And**: hidden older output is indicated
**And**: the long line is truncated
**And**: control characters and ANSI escape sequences do not corrupt the TUI
**And**: the displayed secret-looking assignment is redacted

#### Scenario: Run TUI shows agent liveness during quiet periods

**Given**: an agent process is still running
**And**: the agent has not emitted output for longer than the quiet threshold
**When**: the `run` TUI renders the header, current operation, and activity
**Then**: the agent is shown as quiet but alive
**And**: the last-output or quiet duration is visible
**And**: a non-flooding heartbeat row such as `agent still running` is visible or synthesized
**And**: the quiet state is not shown as failed

#### Scenario: Run agent output is persisted as artifacts

**Given**: a session-level `run` agent step emits stdout and stderr
**When**: the agent step completes, fails, or times out
**Then**: full stdout is persisted to an agent stdout artifact
**And**: full stderr is persisted to an agent stderr artifact
**And**: structured activity entries are persisted for audit/debugging
**And**: TUI tail display does not replace or truncate the persisted artifacts

#### Scenario: Run TUI distinguishes terminal states by finalize gate

**Given**: a run is blocked, failed, or finalized
**When**: the `run` TUI renders the dashboard
**Then**: blocked state uses warning styling and identifies the blocked gate and next action when available
**And**: failed state uses failure styling and points to available command failure evidence
**And**: finalized state uses success styling and renders all six gates complete
**And**: normal non-terminal panel borders do not use warning styling

#### Scenario: Run TUI remains readable in compact terminals

**Given**: the terminal is approximately 80 columns by 24 rows
**When**: the `run` TUI renders the dashboard
**Then**: the layout remains readable without losing run status, `gate x/6`, Finalize path gates, coverage progress, finding counts, blocker state, current operation, recent activity, recent agent output, or implemented controls
**And**: secondary panels may stack vertically if horizontal detail cards would not fit
**And**: Review Gauntlet events and agent output may be mixed chronologically when separate subsections would not fit

#### Scenario: Run TUI waits for explicit dismissal after completion

**Given**: an interactive `run` TUI has started the run controller worker
**When**: the run controller returns a completed, blocked, failed, interrupted, or stopped result
**Then**: the TUI stores that result and renders the final dashboard state instead of immediately exiting
**And**: pressing `q` after completion exits the TUI with the stored result
**And**: pressing `q` while the controller is still active continues to request stop-after-current-step
**And**: non-TUI JSON, no-TUI, non-TTY, and missing-Textual fallback executions keep their existing result emission behavior
