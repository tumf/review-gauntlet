### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL construct review universes from repository-confined files only. Target-scoped path inputs, review universe traversal, target digests, and file digests SHALL reject or omit absolute paths, parent-directory traversal, and symlink escapes that resolve outside the reviewed repository root. Invalid path inputs SHALL fail explicitly rather than being silently interpreted as repository files.

#### Scenario: Target-scoped inventory rejects escaping paths

**Given**: a repository root and a target path list containing `/tmp/escape.py` or `../escape.py`
**When**: the CLI builds target-scoped inventory for a review session
**Then**: the escaping paths are not classified as repository files
**And**: the command fails with an actionable path validation error when the path came from direct user input

#### Scenario: Review universe skips symlink escapes

**Given**: a repository containing a symlink that points to a file outside the repository root
**When**: `review-gauntlet` computes target digest and file digests
**Then**: the external symlink target is not read or hashed
**And**: in-repository regular files remain eligible for review universe hashing

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL create durable run evidence only for review attempts that can evaluate selected cells. A review invocation with no selected current cells SHALL NOT create a run record that can satisfy finalization freshness or reviewed-target evidence. `review-gauntlet review` SHALL return structured failed-cell output when adapter work raises an unexpected exception, not only when the adapter explicitly raises `ReviewAdapterError`. Successful cells from the same run SHALL still persist coverage, findings, occurrences, and applicable fixed-finding verification before the command exits non-zero.

#### Scenario: Zero-cell review does not refresh finalization evidence

**Given**: an active session whose current cells are already reviewed
**When**: the developer runs `review-gauntlet review --budget 1`
**Then**: no new reviewed-cell coverage is recorded
**And**: no zero-cell run is used as the last reviewed target digest for finalization

#### Scenario: Unexpected adapter exception is structured failure

**Given**: an active session where a selected review cell's adapter work raises an unexpected `RuntimeError`
**When**: `review-gauntlet review --format json` processes the run
**Then**: stdout contains a parseable failed-run JSON result with `failed_cell_id` and `failure` details
**And**: the command exits non-zero without printing a raw traceback as the final user-facing result
**And**: the failed cell remains pending or stale for retry

#### Scenario: Unexpected adapter exception preserves other successful cells

**Given**: a review run selects multiple cells
**And**: one selected cell raises an unexpected adapter exception
**And**: at least one other selected cell succeeds
**When**: the run finalizes
**Then**: successful selected cells are recorded as reviewed
**And**: the failed cell remains non-reviewed and visible for later retry

### Requirement: Review rules and prompts SHALL port the pinned OCR corpus

The default review logic SHALL derive its bundled prompts, path-based rules, and line-level review comment contract from Alibaba `open-code-review` commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`. The ported corpus SHALL include OCR's system rule map and all built-in rule documents, SHALL be usable without network access, and SHALL be included in the ruleset digest for stale-coverage detection. Review execution adapters SHALL use this OCR-derived prompt and verdict contract when asking external tools to review cells.

Generated review prompts SHALL identify the target file by repository root, repository-relative file path, content digest, file size in bytes, and line count. Generated prompts SHALL NOT embed the target file body directly. External review tools that need source content SHALL read the target file from the repository path identified in the prompt.

#### Scenario: OCR rule corpus is bundled and traceable

**Given**: the installed `review-gauntlet` package
**When**: the review ruleset is loaded
**Then**: the ruleset records upstream repository `https://github.com/alibaba/open-code-review`
**And**: records upstream commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`
**And**: exposes the default OCR rule map and all OCR rule documents as local package data

#### Scenario: OCR path rule mapping is preserved

**Given**: files named `pom.xml`, `package.json`, `Cargo.toml`, `src/app.ts`, `src/main.rs`, `src/main.c`, and `README.md`
**When**: the default ruleset selects review rules for those paths
**Then**: the selected rule documents match OCR's pinned system rule map
**And**: unmatched paths use OCR's `default.md` rule document

#### Scenario: OCR comments normalize into findings

**Given**: a review adapter returns OCR-style comments with `path`, `content`, `suggestion_code`, `existing_code`, `start_line`, `end_line`, and optional `thinking`
**When**: `review-gauntlet review` records the run
**Then**: each comment is normalized into a session finding occurrence
**And**: comments whose `start_line` and `end_line` are both `0` are preserved as imprecisely positioned findings rather than discarded

#### Scenario: OCR autonomous fix behavior is not adopted

**Given**: OCR plugin guidance can ask an agent to apply fixes after review
**When**: `review-gauntlet review` processes OCR-derived review output
**Then**: the CLI records findings and occurrences only
**And**: it does not modify source files or mark findings fixed automatically

#### Scenario: External command receives OCR-derived review prompt

**Given**: a selected review cell with a file path, content digest, byte size, line count, and rule id
**And**: the session is configured to use an external command adapter
**When**: `review-gauntlet review` invokes the adapter
**Then**: the generated prompt includes the selected OCR-derived rule guidance
**And**: the prompt identifies the file and review cell being evaluated
**And**: the prompt includes the target file path, content digest, byte size, and line count
**And**: the prompt does not embed the target file body
**And**: the prompt instructs the external command to read the target file from the repository path when content is needed
**And**: the prompt instructs the external command to return the OCR-style verdict JSON contract

### Requirement: Review cells SHALL model coverage independently from finding state

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows.

#### Scenario: Unknown review cell update fails

**Given**: a session ledger without cell `RGC-missing`
**When**: internal reconciliation attempts to update `RGC-missing`
**Then**: the store raises an actionable lookup error
**And**: no caller can treat the missing cell as updated coverage

### Requirement: Findings SHALL use stable session-level identity

Finding ID allocation SHALL be deterministic and monotonic within a session. New IDs SHALL NOT be based on the current finding row count because row gaps from migration, repair, or deletion can otherwise reuse an existing human-readable ID.

#### Scenario: Finding id allocation does not reuse gaps

**Given**: a session with existing findings `RGF-0001` and `RGF-0003`
**When**: a new distinct finding is recorded
**Then**: the new finding ID is `RGF-0004`
**And**: no existing finding ID is reused

### Requirement: Finding triage SHALL be explicit and event-backed

Triage event metadata SHALL be validated before persistence. If a developer provides `--until`, the value SHALL be an ISO calendar date. Invalid date metadata SHALL be rejected by `mark` before a finding event is written.

#### Scenario: Mark rejects invalid until date

**Given**: an active session with an open finding
**When**: the developer runs `review-gauntlet mark RGF-0001 waived --until tomorrow`
**Then**: the command fails with a usage error
**And**: no finding event is written for that invalid decision

### Requirement: Fixed findings SHALL require later verification

When the same finding is detected while it is `fixed_pending_verification`, the finding SHALL reopen deterministically and SHALL NOT be immediately verified in the same run that re-detected it. Fixed-pending findings SHALL only become `fixed_verified` after a later review or verification command successfully evaluates the relevant path without detecting the same finding fingerprint.

#### Scenario: Redetected fixed finding remains reopened

**Given**: a finding is `fixed_pending_verification`
**When**: a later review run detects the same finding fingerprint again
**Then**: the finding status becomes `reopened`
**And**: later verification logic in the same run does not transition it to `fixed_verified`

#### Scenario: Fixed finding verifies after dedicated verification command

**Given**: a finding is `fixed_pending_verification`
**And**: its path is successfully evaluated by `review-gauntlet verify-fixes`
**When**: the verification run does not detect the same finding fingerprint
**Then**: the finding status becomes `fixed_verified`
**And**: the transition is recorded as a finding event

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

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

Dirty review-universe blockers SHALL identify that review-universe files are dirty relative to `HEAD` without including individual dirty file paths in `finalize_blockers`.

#### Scenario: Malformed decision metadata blocks finalize without crashing

**Given**: a terminal finding event with malformed JSON metadata or an invalid `until` date
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command returns a structured failure result
**And**: the result includes a blocker for invalid or expired terminal-decision metadata
**And**: no traceback is printed
**And**: no latest checkpoint file is created or overwritten
**And**: no runtime session cleanup or archive is performed

#### Scenario: Successful finalize writes latest checkpoint files

**Given**: an active review session with complete reviewed coverage and all live findings closed
**And**: review-universe files are clean relative to `HEAD`
**And**: the current repository `HEAD` can be resolved to a commit
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: `.review-gauntlet/checkpoints/latest/status.json` is written
**And**: `.review-gauntlet/checkpoints/latest/findings.json` is written
**And**: `.review-gauntlet/checkpoints/latest/events.json` is written
**And**: `.review-gauntlet/checkpoints/latest/summary.md` is written
**And**: stdout contains parseable JSON listing the generated files and checkpoint directory
**And**: the result includes `checkpoint_state: complete`
**And**: the result includes `usable_as_review_base: true`
**And**: the result includes a `review_base_commit` equal to the resolved current `HEAD`
**And**: the result includes `next_required_action: init_next_session`

#### Scenario: Dirty review-universe files block finalize

**Given**: an active review session that otherwise satisfies completion requirements
**And**: an eligible review-universe file has staged, unstaged, deleted, renamed, or untracked changes relative to `HEAD`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with a structured dirty-worktree blocker
**And**: the dirty-worktree blocker does not include the dirty file path
**And**: no latest checkpoint file is created or overwritten
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed

#### Scenario: Dirty review-universe status omits dirty file paths

**Given**: an active review session that otherwise satisfies completion requirements
**And**: an eligible review-universe file has staged, unstaged, deleted, renamed, or untracked changes relative to `HEAD`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: the result includes a structured dirty-worktree blocker in `finalize_blockers`
**And**: the dirty-worktree blocker does not include the dirty file path

#### Scenario: Failed finalize does not update checkpoint or clean up session

**Given**: an active review session with pending review cells, stale review cells, open findings, fixed findings requiring verification, expired terminal decisions, no completed review run, stale target digest evidence, dirty review-universe files, or an unresolved current `HEAD`
**And**: an existing latest checkpoint may already exist
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with structured blockers
**And**: no latest checkpoint file is created or overwritten
**And**: existing latest checkpoint file contents remain unchanged
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed

#### Scenario: Finalize exposes full review state for diff review

**Given**: an active review session with reviewed cells, terminal findings, finding occurrences, and finding events
**When**: the developer runs `review-gauntlet finalize`
**Then**: `status.json` includes checkpoint ID, session metadata, target information, current target digest, last reviewed target digest, ruleset digest, coverage counts, finding state counts, run count, checkpoint state, review base commit, finalization blockers, and next required action
**And**: `findings.json` includes all session findings including terminal findings
**And**: each finding includes latest occurrence line evidence when occurrence evidence exists
**And**: `events.json` includes triage and verification events for the session findings in deterministic order
**And**: `summary.md` presents the same state in a Markdown format suitable for PR review

#### Scenario: Finalize preserves malformed non-terminal event metadata as evidence

**Given**: an active review session with a non-terminal-decision finding event whose metadata is malformed JSON or not a JSON object
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: finalization handles the metadata without a traceback
**And**: `events.json` includes the event with raw metadata evidence when the checkpoint is written
**And**: finalization does not reinterpret the event as a different triage decision

#### Scenario: Finalize publishes checkpoint atomically

**Given**: an active review session eligible for finalization
**And**: an existing `.review-gauntlet/checkpoints/latest/` snapshot may already exist
**When**: the developer runs `review-gauntlet finalize`
**Then**: checkpoint files are generated with matching checkpoint metadata before they become the new `latest/` snapshot
**And**: `status.json`, `findings.json`, `events.json`, and `summary.md` all identify the same checkpoint generation
**And**: a partial generation failure cannot leave a mixed-generation latest checkpoint consumable by the next `init`

#### Scenario: Finalize is latest-only by default

**Given**: an active review session eligible for finalization
**And**: an existing `.review-gauntlet/checkpoints/latest/` snapshot
**When**: the developer runs `review-gauntlet finalize`
**Then**: the command overwrites the same latest snapshot files atomically
**And**: no timestamped or session-history checkpoint directory is created by default

#### Scenario: Successful finalize prevents continuing the old active session

**Given**: an active review session eligible for finalization
**When**: the developer runs `review-gauntlet finalize`
**Then**: the active session marker is removed or invalidated after checkpoint files are written
**And**: subsequent `review-gauntlet review` without a new `init` fails with an actionable message
**And**: subsequent `review-gauntlet status` without a new `init` fails with an actionable message
**And**: neither command silently advances or reports the finalized old session as active

### Requirement: Existing planning commands SHALL remain compatible

Documentation for planning diagnostics SHALL use the current `--format json` output flag and SHALL NOT instruct users to run removed `--json` flags. Markdown report rendering SHALL preserve table structure by escaping or normalizing dynamic table-cell values such as IDs, statuses, checks, and evidence. Legacy planning diagnostics SHALL apply the same default review-path exclusions used by review session target planning when building review plans and report matrices. The general `inventory` diagnostic SHALL remain broader and continue to show non-artifact project files that may be excluded from review planning.

#### Scenario: Documentation uses current planning flags

**Given**: a reader follows repository smoke-command guidance
**When**: they run the documented inventory or plan JSON command
**Then**: the command uses `--format json`
**And**: the command is accepted by the current parser

#### Scenario: Report escapes table separators

**Given**: a review matrix row whose evidence contains a pipe character or newline
**When**: `review-gauntlet report` renders markdown output
**Then**: the coverage matrix remains a valid four-column markdown table
**And**: evidence content is preserved in escaped or normalized form

#### Scenario: Plan excludes default review noise

**Given**: a repository containing eligible source files, `openspec/`, `tests/`, `docs/`, conventional test files, and package manifest or lock files
**When**: the developer runs `review-gauntlet plan --format json`
**Then**: stdout contains a parseable review plan for eligible review files
**And**: the plan does not include files excluded by the default review-path filter
**And**: the same excluded paths remain visible to the broader `review-gauntlet inventory` diagnostic when they are not artifact-excluded

#### Scenario: Report matrix derives from filtered review plan

**Given**: a repository containing eligible source files and default review-path-excluded files
**When**: the developer runs `review-gauntlet report --format json`
**Then**: stdout contains a parseable matrix derived only from filtered review-plan slices
**And**: checks are not emitted solely for files excluded from review planning

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

Command adapter configuration validation SHALL reject invalid environment variable names and SHALL define how literal braces are represented in template-bearing strings. Configuration errors SHALL be reported before adapter execution. Adapter `cwd` settings SHALL resolve under the reviewed repository root and cwd values that resolve outside the repository SHALL be rejected before executing any adapter command.

Review execution SHALL resolve configuration using deterministic precedence: built-in defaults, then global config, then project config, then explicit CLI config/options. Global config SHALL be discovered from `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` or fallback `~/.config/review-gauntlet/config.jsonc`. Project config SHALL prefer `.review-gauntlet/config.jsonc` and support `review-gauntlet.jsonc` for compatibility. Existing JSON config discovery MAY remain supported for backward compatibility. When multiple configuration layers are combined, objects SHALL deep merge, scalars SHALL use the last writer, and arrays SHALL replace earlier arrays. When no usable config is available, the failure guidance SHALL point to `review-gauntlet config preset list` for available bundled presets.

Explicit `--config` SHALL accept both absolute paths and repository-relative paths. Relative explicit config paths SHALL resolve under the reviewed repository root. Absolute explicit config paths MAY point outside the repository, but the resolved path SHALL exist and be a regular file. Explicit config SHALL take precedence over global and project discovery.

Command adapter output path templates SHALL be deterministic before prompt construction. `adapter.output.path` SHALL reject `{prompt}` because the prompt itself can contain the output path and would make prompt-time and read-time path resolution diverge. The `{prompt}` template variable SHALL remain supported for adapter `args` and `env`.

<!-- Expected canonical result after archive: missing-config guidance points to `review-gauntlet config preset list` instead of `review-gauntlet config list`. -->

#### Scenario: Missing config guidance is actionable

**Given**: no fixture, explicit config, project config, or global config is available
**When**: the developer runs `review-gauntlet review`
**Then**: the command fails with a usage error explaining that no Review Gauntlet config was found
**And**: the message shows how to create a project config with `review-gauntlet config init --preset opencode`
**And**: the message shows how to create a global config with `review-gauntlet config init --global --preset opencode`
**And**: the message points to `review-gauntlet config preset list` for available presets

### Requirement: Command adapter SHALL invoke external tools safely and preserve artifacts

Command adapter artifact paths SHALL remain confined to the deterministic per-run cell artifact tree. Review cell IDs loaded from persisted state SHALL NOT be trusted as filesystem paths; malformed IDs containing path separators or parent traversal SHALL fail before artifact directories are created outside the cell artifact root.

For file-json output, the command adapter SHALL prepare nested output destination directories after validating that the resolved output file remains inside the selected cell artifact directory. This preparation SHALL happen before the external command is invoked.

#### Scenario: Unsafe cell id cannot escape artifact directory

**Given**: a command adapter receives a review cell whose ID contains `../`
**When**: the adapter prepares per-cell artifacts
**Then**: the adapter fails with a structured safety error
**And**: no artifact is written outside `.review-gauntlet/runs/<run_id>/cells/`

#### Scenario: Nested file-json output path is writable

**Given**: a command adapter config with `output.path` set to `out/verdict.json`
**When**: `review-gauntlet review` invokes the adapter for a selected cell
**Then**: the adapter creates the `out/` directory under that cell's artifact directory before command execution
**And**: a command that writes valid verdict JSON to that configured file can complete successfully

#### Scenario: Unsafe output path still has no filesystem side effect

**Given**: a command adapter config whose output path resolves outside the cell artifact directory
**When**: the adapter resolves the output path
**Then**: the adapter fails with a structured safety error
**And**: it does not create parent directories outside the cell artifact directory

### Requirement: Command verdicts SHALL normalize through OCR comments only

External command adapter verdict comments SHALL be validated against the selected review cell before they affect findings or coverage. Each precise comment SHALL target the selected cell path and use a line range within the reviewed file. OCR-style imprecise comments with `start_line=0` and `end_line=0` SHALL remain valid.

#### Scenario: Cross-cell verdict comment is rejected

**Given**: a selected review cell for `src/app.py`
**And**: the external command emits a valid JSON verdict whose comment path is `src/other.py`
**When**: `review-gauntlet review` processes the verdict
**Then**: no finding occurrence is created from that comment
**And**: the selected cell is not marked reviewed
**And**: the review command exits non-zero with failure artifacts preserved

#### Scenario: Out-of-range verdict comment is rejected

**Given**: a selected review cell with ten lines
**And**: the external command emits a precise comment ending at line 999
**When**: `review-gauntlet review` processes the verdict
**Then**: the verdict is rejected as outside the review cell
**And**: coverage is not recorded for that cell

#### Scenario: Imprecise OCR verdict comment remains valid

**Given**: a selected review cell
**And**: the external command emits a comment for that cell with `start_line=0` and `end_line=0`
**When**: `review-gauntlet review` processes the verdict
**Then**: the comment is recorded as an imprecise finding occurrence
**And**: successful coverage can be recorded for the selected cell

#### Scenario: Malformed command verdict is rejected

**Given**: a command adapter returns unparseable JSON or a JSON object that does not match the verdict contract
**When**: `review-gauntlet review` processes the adapter result
**Then**: no finding occurrence is created from that result
**And**: the selected cell is not marked reviewed
**And**: the review command exits non-zero with failure artifacts preserved

### Requirement: CI runtime SHALL be pinned to the project Python version

Repository CI SHALL install the Python runtime declared by project guidance rather than the latest interpreter available to the package manager.

#### Scenario: CI installs Python 3.11

**Given**: the GitHub Actions workflow for repository checks
**When**: CI sets up Python with `uv`
**Then**: the workflow installs Python 3.11 explicitly
**And**: dependency resolution, linting, type checking, and tests run against that runtime

### Requirement: Bootstrap instructions SHALL avoid mutable remote code execution

Repository bootstrap scripts SHALL NOT execute mutable remote installer content directly without pinning or integrity verification. If an automatic installer is used, the downloaded artifact SHALL be pinned and verified before execution; otherwise the script SHALL fail closed with an actionable instruction.

#### Scenario: Worktree setup does not pipe latest installer to shell

**Given**: a developer runs `.wt/setup` in a new worktree without the required hook tool installed
**When**: the setup script reaches hook installation
**Then**: it does not execute `curl ... | sh` from a mutable latest URL
**And**: it either verifies a pinned installer before execution or fails with instructions to install the tool manually

### Requirement: README design documentation SHALL describe implemented review execution

The README Design section SHALL reflect the current implemented capabilities: inventory/plan/report diagnostics, durable review sessions, command adapter execution, finding tracking, and finalization.

#### Scenario: README design section is current

**Given**: a reader opens the README Design section
**When**: they read the closing design description
**Then**: it does not claim that the project only creates inventory, plans, and matrices
**And**: it acknowledges the implemented session lifecycle and external command adapter support

### Requirement: Verify-fixes command SHALL re-review fixed findings explicitly

`review-gauntlet verify-fixes` SHALL provide a dedicated post-fix verification command for findings in `fixed_pending_verification`. The command SHALL execute at most one verification run, SHALL use the existing review adapter verdict contract, SHALL only target fixed-pending findings selected by optional filters, and SHALL keep findings that cannot be evaluated visible rather than treating them as verified.

#### Scenario: Verify fixes verifies absent findings

**Given**: an active session with a finding in `fixed_pending_verification`
**And**: the finding's path maps to a current review cell
**And**: the verification adapter returns no comment with the finding's fingerprint
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: the command executes a verification run for the relevant current review cell
**And**: the finding transitions to `fixed_verified`
**And**: stdout contains parseable JSON listing the finding ID in `fixed_verified_ids`
**And**: the command exits `0`

#### Scenario: Verify fixes reopens redetected findings

**Given**: an active session with a finding in `fixed_pending_verification`
**And**: the finding's path maps to a current review cell
**And**: the verification adapter returns a comment that normalizes to the same finding fingerprint
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: the finding transitions to `reopened`
**And**: the finding does not transition to `fixed_verified` in the same run
**And**: stdout contains parseable JSON listing the finding ID in `reopened_ids`
**And**: the command exits `1`

#### Scenario: Verify fixes targets only fixed-pending findings

**Given**: an active session with pending review cells and findings in `confirmed`, `reopened`, `fixed_pending_verification`, and terminal states
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: adapter execution is limited to current cells needed by `fixed_pending_verification` findings
**And**: unrelated pending or stale review cells are not selected merely to advance coverage
**And**: non-fixed-pending findings are not mutated

#### Scenario: Verify fixes supports focused finding and path filters

**Given**: an active session with multiple findings in `fixed_pending_verification` across multiple repository paths
**When**: the developer runs `review-gauntlet verify-fixes --finding RGF-0001 --path src/app.py --format json`
**Then**: only fixed-pending findings matching the requested finding ID and repository path filter are targeted
**And**: repeated `--finding` values match any listed finding ID
**And**: repeated `--path` values match any listed safe repository path or prefix

#### Scenario: Verify fixes rejects unsafe path filters before execution

**Given**: an active session with fixed-pending findings
**When**: the developer runs `review-gauntlet verify-fixes --path ../src`
**Then**: the command fails with a usage error
**And**: no adapter command is executed
**And**: no run or finding event is written

#### Scenario: Verify fixes no-op does not refresh evidence

**Given**: an active session with matching fixed-pending findings
**When**: the developer runs `review-gauntlet verify-fixes --budget 0 --format json`
**Then**: no verification run is created
**And**: no finding state is modified
**And**: stdout reports the targeted finding IDs as still requiring verification

#### Scenario: Verify fixes reports unverifiable findings

**Given**: an active session with a fixed-pending finding whose path cannot be successfully evaluated
**When**: the developer runs `review-gauntlet verify-fixes --format json`
**Then**: the finding remains `fixed_pending_verification`
**And**: stdout contains parseable JSON listing the finding ID in `unverifiable_ids`
**And**: the command exits `1`

### Requirement: CLI SHALL expose package version without repository state

`review-gauntlet` SHALL provide a top-level `--version` flag that reports the package version from the existing package version source and exits successfully without requiring repository-root validation, active review-session state, adapter configuration, or review work.

#### Scenario: Version flag prints package version

**Given**: an installed or development invocation of the `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet --version`
**Then**: stdout contains exactly `review-gauntlet <version>` followed by a newline, where `<version>` is the value exported from `review_gauntlet.__about__.__version__`
**And**: the command exits with code `0`

#### Scenario: Version flag bypasses repository validation

**Given**: the current working directory does not need to be a review target or active session root
**When**: the developer runs `review-gauntlet --version`
**Then**: the CLI prints the package version before attempting root path validation or session-store access
**And**: no review-gauntlet state directory or adapter configuration is required

#### Scenario: Existing subcommands keep their parser behavior

**Given**: the existing `review-gauntlet` subcommands and flags
**When**: developers run supported subcommands such as `inventory`, `plan`, `report`, `init`, `review`, `verify-fixes`, `status`, `findings`, `mark`, or `finalize`
**Then**: their accepted arguments, usage errors, output formats, and session behavior remain unchanged by the version flag

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL be the diff from that checkpoint's `review_base_commit` to `HEAD`. If no latest checkpoint exists, the default target SHALL include all eligible repository files. If a latest checkpoint exists but cannot safely be used, `init` SHALL fail explicitly instead of silently falling back. This is a breaking change from the previous bare-`init` worktree default; callers that require worktree review SHALL pass `--worktree` explicitly.

#### Scenario: Init defaults to latest checkpoint diff when available

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists
**And**: the latest checkpoint files share consistent checkpoint metadata
**And**: the checkpoint contains `usable_as_review_base: true`
**And**: the checkpoint contains a `review_base_commit` that resolves to a commit in the current repository
**And**: `review_base_commit` is an ancestor of `HEAD`
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the initialized session target is equivalent to `--from <review_base_commit> --to HEAD`
**And**: review cells are scoped to files changed between that commit and `HEAD`

#### Scenario: Init defaults to all files when no checkpoint exists

**Given**: `.review-gauntlet/checkpoints/latest/status.json` does not exist
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the initialized session target is equivalent to `--all`
**And**: review cells are built from all eligible repository files

#### Scenario: Init rejects invalid latest checkpoint instead of falling back

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists
**And**: the checkpoint is malformed, internally inconsistent, has `usable_as_review_base` other than `true`, lacks `review_base_commit`, references a commit that cannot be resolved, or references a commit that is not an ancestor of `HEAD`
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the command fails with an actionable checkpoint error
**And**: no all-files fallback session is created

#### Scenario: Explicit init target flags override checkpoint default

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists and is usable
**When**: the developer runs `review-gauntlet init --all`, `review-gauntlet init --worktree`, `review-gauntlet init --from main --to HEAD`, or `review-gauntlet init --commit <commit>`
**Then**: the explicit target mode is used
**And**: the latest checkpoint does not override that explicit target selection

#### Scenario: Checkpoint files are the only tracked review-gauntlet state

**Given**: repository ignore rules for `.review-gauntlet` state
**When**: finalize writes checkpoint files under `.review-gauntlet/checkpoints/latest/`
**Then**: those checkpoint files are eligible for Git tracking
**And**: `.review-gauntlet/ledger.sqlite` remains ignored
**And**: `.review-gauntlet/active-session.json` remains ignored
**And**: `.review-gauntlet/runs/` remains ignored
**And**: `.review-gauntlet/rules.lock` remains ignored
**And**: `.review-gauntlet/archive/` remains ignored
**And**: checkpoint history directories other than `latest/` remain ignored

### Requirement: Ready command SHALL emit the next skill-directed prompt

`review-gauntlet ready` SHALL inspect the active review session and emit at most one short prompt for the next externally-orchestrated review task. The command SHALL NOT mutate review session state, finding state, review cell state, checkpoint files, or git state. JSON output SHALL contain only a `prompt` key whose value is a string or `null`; text output SHALL print only the prompt body or `no ready task`.

#### Scenario: Ready emits prompt-only JSON for untriaged findings

**Given**: an active review session with one or more untriaged findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON with exactly the key `prompt`
**And**: `prompt` is a non-empty string that begins with `Use the review-gauntlet task execution skill.`
**And**: the prompt directs the agent to triage untriaged findings
**And**: the prompt states a stop condition for when no untriaged findings remain

#### Scenario: Ready emits text prompt without metadata labels

**Given**: an active review session with ready work
**When**: the developer runs `review-gauntlet ready --format text`
**Then**: stdout contains the selected prompt body
**And**: stdout does not include task IDs, claim instructions, queue metadata, or JSON wrapper fields

#### Scenario: Ready emits no prompt when no ready work exists

**Given**: an active review session with no actionable ready prompt
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: stdout contains parseable JSON equal to `{"prompt": null}`
**And**: the command exits successfully

#### Scenario: Ready prompt priority is deterministic

**Given**: an active review session with multiple kinds of incomplete work
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the selected prompt corresponds to the first available category in this order: stale review cells, pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, finalize
**And**: finding prompts remain reachable after review-cell coverage is complete.

#### Scenario: Ready leaves status output unchanged

**Given**: an active review session
**When**: the developer runs `review-gauntlet status --format json`
**Then**: the status output schema remains the existing status schema
**And**: no `prompt` field is added to status output

#### Scenario: Ready is read-only

**Given**: an active review session with findings, review cells, runs, events, and no latest checkpoint generated by this command
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: no review run is created
**And**: no review cell state is changed
**And**: no finding state is changed
**And**: no finding event is written
**And**: no checkpoint file is written
**And**: no git mutation is performed

#### Scenario: Finalize prompt instructs commit before finalization

**Given**: an active review session whose review coverage and live finding dependencies are resolved enough for finalization work to be the next task
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: `prompt` is a non-empty string that begins with `Use the review-gauntlet task execution skill.`
**And**: the prompt directs the agent to finalize the review-gauntlet session
**And**: the prompt instructs the agent to commit intended git changes before finalizing

### Requirement: Review configuration SHALL support XDG global fallback

`review-gauntlet` SHALL discover command adapter configuration from XDG global config paths when no explicit config path and no repository-local config file is available. Repository-local config files SHALL keep their existing precedence over global config files, and explicit `--config` SHALL remain the highest-precedence source. Global discovery SHALL be read-only and SHALL NOT create config directories or files.

#### Scenario: Global XDG config is used when repo config is absent

**Given**: a repository without `.review-gauntlet/config.jsonc`, `.review-gauntlet/config.json`, `review-gauntlet.jsonc`, or `review-gauntlet.json`
**And**: `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` exists with a valid command adapter config
**When**: `review-gauntlet review` or `review-gauntlet verify-fixes` loads adapter configuration without `--config`
**Then**: the global XDG config is loaded
**And**: no repository-local config file is created

#### Scenario: Repo-local config overrides global config

**Given**: a repository with `.review-gauntlet/config.jsonc`
**And**: `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` also exists
**When**: `review-gauntlet` loads adapter configuration without `--config`
**Then**: the repository-local `.review-gauntlet/config.jsonc` config is loaded
**And**: the global config is ignored

#### Scenario: Home config is used when XDG_CONFIG_HOME is unset

**Given**: `XDG_CONFIG_HOME` is unset or empty
**And**: `~/.config/review-gauntlet/config.jsonc` exists with a valid command adapter config
**And**: no explicit or repository-local config exists
**When**: `review-gauntlet` loads adapter configuration without `--config`
**Then**: the home config is loaded

### Requirement: Config validation and effective config inspection SHALL be available

The `review-gauntlet config` command group SHALL validate configuration files and SHOULD expose the resolved effective configuration for debugging and automation.

#### Scenario: Discovered configuration validates successfully

**Given**: a repository or user environment with a valid discoverable Review Gauntlet config
**When**: the developer runs `review-gauntlet config validate`
**Then**: the command validates JSONC parsing and schema constraints
**And**: the command exits `0`

#### Scenario: Explicit configuration validates successfully

**Given**: `/tmp/review-gauntlet.jsonc` exists and contains a valid Review Gauntlet config
**When**: the developer runs `review-gauntlet config validate --config /tmp/review-gauntlet.jsonc`
**Then**: the command validates that explicit config file
**And**: the command exits `0`

#### Scenario: Invalid configuration fails validation before adapter execution

**Given**: a config file whose command adapter command contains whitespace as a shell string
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: the command fails with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Effective config is displayed

**Given**: a global config and a project config are both present
**When**: the developer runs `review-gauntlet config effective`
**Then**: stdout displays the final merged configuration
**And**: the output reflects project config precedence over global config

### Requirement: Git worktree sessions SHALL isolate review work by session

`review-gauntlet init --git-worktree` SHALL create a Git-worktree-backed review session without changing existing target-selection semantics. The existing `init --worktree` flag SHALL continue to mean workspace-diff target selection. `--git-worktree` SHALL be composable with existing target modes, including `--worktree`.

A Git-worktree-backed session SHALL record enough durable metadata to later verify and finalize the session branch: base branch, base commit, session branch, worktree path, and whether Git worktree mode is enabled. Branch names and worktree paths SHALL be generated from path-safe session identifiers and scoped to Review Gauntlet-owned namespaces by default.

#### Scenario: Init creates a session branch and linked worktree

**Given**: a developer is in a Git repository on branch `main` with a resolvable `HEAD`
**When**: they run `review-gauntlet init --git-worktree --format json`
**Then**: a unique session branch under a Review Gauntlet-owned branch namespace is created
**And**: a linked Git worktree for that session branch is created under a Review Gauntlet-owned worktree directory
**And**: the session metadata records `git_worktree.enabled: true`, `base_branch`, `base_commit`, `session_branch`, and `worktree_path`
**And**: stdout includes the session branch and worktree path evidence

#### Scenario: Existing worktree target semantics are preserved

**Given**: a repository with staged, unstaged, or untracked workspace changes
**When**: the developer runs `review-gauntlet init --worktree --format json`
**Then**: Review Gauntlet selects the workspace-diff review target as before
**And**: no Git linked worktree is created solely because `--worktree` was provided

#### Scenario: Workspace-diff targeting composes with Git worktree isolation

**Given**: a repository with staged, unstaged, or untracked workspace changes
**When**: the developer runs `review-gauntlet init --worktree --git-worktree --format json`
**Then**: the review target is the workspace-diff target
**And**: a session branch and linked Git worktree are created for the session
**And**: the session metadata records both the workspace-diff target and Git-worktree session metadata

### Requirement: Finalize merge SHALL merge and clean up Git worktree sessions

`review-gauntlet finalize --merge` SHALL be the completion path for Git-worktree-backed sessions. It SHALL first enforce all normal finalization blockers. When those blockers are absent, it SHALL write checkpoint artifacts, commit intended session branch changes including checkpoint artifacts, merge the session branch into the recorded base branch, finalize the session, clear the active session marker, remove the linked session worktree, and delete the session branch.

`finalize --merge` SHALL produce structured output that distinguishes checkpoint success, merge success, and cleanup success. Merge blockers SHALL leave the active session, session branch, and session worktree available for repair. Cleanup failures after a successful merge SHALL NOT pretend the merge failed, but SHALL report cleanup blockers and a follow-up cleanup action.

#### Scenario: Finalize merge completes checkpoint, merge, and cleanup

**Given**: an active Git-worktree-backed review session with complete reviewed coverage and all live findings closed
**And**: review-universe files are clean relative to session branch `HEAD`
**And**: the recorded base branch exists, is clean, and still points at the recorded base commit
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: checkpoint artifacts are written for the session
**And**: the checkpoint artifacts and intended session changes are committed on the session branch
**And**: the session branch is merged into the recorded base branch
**And**: the result includes `merged: true`, the recorded base branch, the session branch, and the resulting merge commit
**And**: the active session marker is removed or invalidated
**And**: the linked session worktree is removed
**And**: the session branch is deleted
**And**: the result includes `cleaned_up: true` with removed worktree and deleted branch evidence

#### Scenario: Finalize merge rejects non Git-worktree sessions

**Given**: an active review session that was not created with `--git-worktree`
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: the command fails with a structured blocker explaining that merge finalization requires a Git-worktree-backed session
**And**: no checkpoint file is created solely because `--merge` was requested
**And**: no branch merge or cleanup is attempted
**And**: the active session marker remains usable for continuing review work

#### Scenario: Merge blockers preserve repairable session state

**Given**: an active Git-worktree-backed review session that otherwise satisfies normal finalization requirements
**And**: the recorded base branch is missing, dirty, advanced beyond the recorded base commit, the session branch is missing, the session worktree is missing, or the session branch cannot merge cleanly
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: the command fails with structured merge blockers
**And**: the result includes `merged: false`
**And**: no cleanup of the session branch or session worktree is performed
**And**: the active session marker remains usable for continuing or repairing the session

#### Scenario: Cleanup failure after merge is reported without hiding merge success

**Given**: an active Git-worktree-backed review session eligible for `finalize --merge`
**And**: the session branch is successfully merged into the recorded base branch
**And**: removing the session worktree or deleting the session branch fails
**When**: `review-gauntlet finalize --merge --format json` returns
**Then**: the result includes `merged: true`
**And**: the result includes `cleaned_up: false`
**And**: the result includes cleanup blocker evidence
**And**: the result includes `next_required_action: cleanup_git_worktree`
**And**: the session is recorded as finalized rather than active

### Requirement: CLI documentation SHALL distinguish target worktree from Git worktree isolation

Review Gauntlet CLI help and documentation SHALL distinguish `init --worktree` as workspace-diff target selection from `init --git-worktree` as Git linked worktree session isolation. Documentation SHALL describe `finalize --merge` as the operation that merges and cleans up Git-worktree-backed sessions.

#### Scenario: Help exposes both worktree concepts without ambiguity

**Given**: an installed or development invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet init --help`
**Then**: help text describes `--worktree` as reviewing workspace changes
**And**: help text describes `--git-worktree` as creating an isolated Git worktree and session branch

#### Scenario: Documentation shows merge cleanup workflow

**Given**: a developer reads repository usage documentation
**When**: they follow the Git-worktree-backed session workflow
**Then**: the documentation shows `review-gauntlet init --git-worktree`
**And**: the documentation shows `review-gauntlet finalize --merge`
**And**: the documentation explains that successful merge finalization removes the session worktree and deletes the session branch
