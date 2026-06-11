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

### Requirement: Review rules and prompts SHALL port the pinned OCR corpus

The default review logic SHALL derive its bundled prompts, path-based rules, and line-level review comment contract from Alibaba `open-code-review` commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`. The ported corpus SHALL include OCR's system rule map and all built-in rule documents, SHALL be usable without network access, and SHALL be included in the ruleset digest for stale-coverage detection. Review execution adapters SHALL use this OCR-derived prompt and verdict contract when asking external tools to review cells.

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

**Given**: a selected review cell with a file path, content digest, and rule id
**And**: the session is configured to use an external command adapter
**When**: `review-gauntlet review` invokes the adapter
**Then**: the generated prompt includes the selected OCR-derived rule guidance
**And**: the prompt identifies the file and review cell being evaluated
**And**: the prompt instructs the external command to return the OCR-style verdict JSON contract

### Requirement: Review cells SHALL model coverage independently from finding state

The CLI SHALL track review cells as review coverage units separate from finding triage state. A cell MAY be reviewed while the session remains incomplete because associated findings are not terminal. Review coverage for current cells SHALL be tied to the reviewed content digest: when a stale current cell is successfully reviewed again, the ledger SHALL refresh that cell's stored digest to the current digest so that unchanged content is not repeatedly marked stale.

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

#### Scenario: Successful stale review refreshes the reviewed digest

**Given**: an active session where a previously reviewed current cell has become stale because its file content changed
**When**: a later `review-gauntlet review` run successfully reviews that current cell
**Then**: the cell is recorded as `reviewed`
**And**: the cell's stored content digest is refreshed to the current digest that was reviewed
**And**: a later review run without another file change does not mark that same cell stale again
**And**: the later review run can select remaining pending or stale cells according to normal budget order

#### Scenario: Unsuccessful stale review does not refresh coverage

**Given**: an active session where a previously reviewed current cell has become stale because its file content changed
**When**: a later `review-gauntlet review` run fails, is interrupted, or does not select that cell
**Then**: the cell is not recorded as refreshed reviewed coverage
**And**: the stale or pending coverage remains visible until a successful review evaluates the current cell

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

The session workflow SHALL preserve the existing `inventory`, `plan`, and `report` command concepts while making legacy planning command output selection explicit. `inventory` and `plan` SHALL accept `--format json|text`, default to `text`, and SHALL no longer accept the legacy `--json` flag. JSON output for `inventory --format json` and `plan --format json` SHALL remain parseable using the existing Pydantic JSON contracts. `report --format text` SHALL emit the existing Markdown-style review matrix report body. Inventory generation SHALL exclude review-gauntlet-generated session state, common cache/build/editor artifacts, and files ignored by Git when Git-backed discovery is available, so coverage reflects the project review target rather than generated tool state. User-facing README command guidance SHALL present the session workflow as the primary review path and document `inventory`, `plan`, and `report` as diagnostic or legacy planning inspection commands rather than the first day-to-day entry points.

<!-- Expected canonical result after archive: the planning command compatibility requirement documents `--format json|text` for inventory/plan, default text output, removal of the legacy `--json` flag, retained report behavior, and README guidance that places planning commands after the primary session workflow as diagnostic inspection commands. -->

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

#### Scenario: README leads with session workflow

**Given**: a reader opens the README command guidance
**When**: they follow the first operational Review Gauntlet review workflow shown after setup
**Then**: the guidance starts with session initialization through `review-gauntlet init`
**And**: it continues through one `review-gauntlet review` run and related session-state commands before introducing `inventory`, `plan`, or `report`

#### Scenario: Planning commands are documented as diagnostics

**Given**: a reader needs to inspect file discovery, slicing, or report rendering
**When**: they read the README command guidance for `inventory`, `plan`, and `report`
**Then**: those commands are still documented with example invocations
**And**: the wording identifies them as diagnostic, inspection, or legacy planning commands rather than the primary review lifecycle

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

`review-gauntlet` SHALL support external review execution through a JSON or JSONC command adapter configuration. The configuration SHALL identify the command, argv arguments, optional output mode, and optional timeout/cwd/env settings without requiring in-process LLM SDK dependencies. The generated OCR-derived prompt SHALL be available as the `{prompt}` template variable for argv/env expansion. Command adapter configuration SHALL NOT include an `input` section or prompt-file transport mode. When output configuration is omitted, the adapter SHALL default to file-backed verdict output using the per-cell output artifact path.

#### Scenario: Review loads explicit adapter config

**Given**: an active review session
**And**: a valid command adapter configuration file at `/tmp/review-gauntlet.jsonc`
**When**: the developer runs `review-gauntlet review --config /tmp/review-gauntlet.jsonc`
**Then**: the review command uses that configuration for external command execution
**And**: no repository default config path overrides it

#### Scenario: Review discovers repository adapter config

**Given**: an active review session
**And**: no `--config` argument
**And**: config files may exist at `.review-gauntlet/config.jsonc`, `.review-gauntlet/config.json`, `review-gauntlet.jsonc`, and `review-gauntlet.json`
**When**: the developer runs `review-gauntlet review`
**Then**: the review command selects the first existing valid config in that precedence order

#### Scenario: JSONC config is accepted

**Given**: a command adapter config containing `//` line comments, `/* */` block comments, and trailing commas
**When**: the review command loads the config
**Then**: the config is parsed as JSONC
**And**: comment-like text inside JSON strings remains unchanged

#### Scenario: Missing command config does not implicitly execute a tool

**Given**: an active review session
**And**: no `--fixture` argument
**And**: no command adapter configuration is available
**When**: the developer runs `review-gauntlet review`
**Then**: the command fails with an actionable configuration error
**And**: it does not implicitly execute `opencode`, `claude`, `codex`, or any other default external tool

#### Scenario: Prompt template is accepted in argv

**Given**: a valid command adapter configuration whose `args` include `{prompt}`
**When**: the review command loads the config
**Then**: `{prompt}` is accepted as a supported template variable
**And**: `{prompt_file}` is rejected as an unsupported template variable
**And**: no `input` or `input.mode` field is accepted in the config

#### Scenario: Timeout defaults to 600 seconds

**Given**: a valid command adapter configuration without `timeout_seconds`
**When**: the review command loads the config
**Then**: the command adapter timeout defaults to 600 seconds
**And**: explicitly configured non-positive timeout values remain invalid

#### Scenario: Process context controls are optional

**Given**: a valid command adapter configuration without `cwd` or `env`
**When**: the review command invokes the command adapter
**Then**: the external process inherits the parent process cwd
**And**: the external process inherits the parent process environment without automatic fixed env injection
**And**: explicit `cwd` and `env` values remain supported when configured

#### Scenario: Output config defaults to file-json

**Given**: a valid command adapter configuration without an `output` section
**When**: the review command evaluates a cell
**Then**: the adapter treats the effective output mode as `file-json`
**And**: the effective verdict path is the deterministic per-cell output artifact path

### Requirement: Command adapter SHALL invoke external tools safely and preserve artifacts

The command adapter SHALL invoke configured tools without a shell, SHALL expose generated prompts through `{prompt}` argv/env template expansion, SHALL collect verdicts from stdout JSON when explicitly configured or from file JSON by default, and SHALL preserve per-cell artifacts for auditability. In file-json mode, stdout and stderr SHALL be preserved as logs but SHALL NOT be parsed or trusted as verdict input.

#### Scenario: Command adapter executes without shell

**Given**: a valid command adapter configuration with `command` and `args` as structured values
**When**: `review-gauntlet review` invokes the command adapter
**Then**: the process is executed without `shell=True`
**And**: configured arguments are passed as an argv array
**And**: shell metacharacters in paths, arguments, or generated prompt text are not interpreted by a shell

#### Scenario: Command adapter expands generated prompt as argv element

**Given**: a command adapter configuration whose args include `{prompt}`
**When**: a review cell is evaluated
**Then**: `review-gauntlet` expands `{prompt}` to the generated OCR-derived prompt as one argv element
**And**: the command adapter does not send the prompt through stdin as a transport side effect
**And**: the command adapter does not pass a prompt file as a transport side effect

#### Scenario: Command adapter supports stdout-json output

**Given**: a command adapter configuration explicitly using output mode `stdout-json`
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict emitted to stdout
**And**: non-JSON stdout text remains invalid verdict output

#### Scenario: Command adapter defaults to file-json output

**Given**: a command adapter configuration without an output mode
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict written to the default per-cell output file
**And**: stdout content is preserved but ignored for verdict parsing

#### Scenario: Command adapter supports explicit file-json output paths

**Given**: a command adapter configuration using output mode `file-json`
**And**: the configured output path includes `{output_file}` or another safe artifact-local path
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict written to the output file

#### Scenario: File-json ignores noisy stdout

**Given**: a command adapter configuration using file-json output
**And**: the external command writes valid verdict JSON to the output file
**And**: the external command writes progress text, reasoning text, or other non-JSON text to stdout
**When**: a review cell is evaluated
**Then**: the adapter validates the output file verdict
**And**: stdout noise does not cause an invalid verdict failure

#### Scenario: Review artifacts are persisted per evaluated cell

**Given**: a review run evaluates a cell through the command adapter
**When**: command execution finishes or fails
**Then**: `review-gauntlet` preserves the generated prompt, command metadata, stdout, stderr, and verdict or failure details under a deterministic run/cell artifact path
**And**: the artifact path is associated with the review run evidence

#### Scenario: Unsafe output paths are rejected

**Given**: a command adapter configuration with file-json output
**When**: the configured output path would escape the intended run or cell artifact area through traversal, absolute unsafe paths, or unsupported template expansion
**Then**: the review command rejects the configuration or run before trusting the output
**And**: the cell is not marked reviewed

### Requirement: Command verdicts SHALL normalize through OCR comments only

External command adapter verdicts SHALL be JSON objects containing a `comments` array whose entries validate as OCR-style comments before they can affect findings or coverage. The verdict source SHALL be the configured output transport: stdout only for explicit stdout-json mode, and the verdict file for file-json mode.

#### Scenario: Valid command verdict creates finding occurrences

**Given**: a command adapter verdict with one valid OCR-style comment
**When**: `review-gauntlet review` processes the verdict
**Then**: the comment is validated against the OCR comment model
**And**: the existing finding normalization and deduplication path records the finding occurrence
**And**: the finding remains untriaged until explicitly marked

#### Scenario: Empty command verdict reviews the cell without findings

**Given**: a command adapter verdict with an empty `comments` array
**When**: `review-gauntlet review` processes the verdict
**Then**: the selected cell can be marked reviewed
**And**: no finding occurrence is created for that cell

#### Scenario: Invalid file-json verdict is not rescued from stdout

**Given**: a command adapter using file-json output
**And**: the configured output file is missing or contains an invalid verdict
**And**: stdout contains valid JSON or other text
**When**: `review-gauntlet review` processes the adapter result
**Then**: no finding occurrence is created from stdout
**And**: the selected cell is not marked reviewed
**And**: the review command exits non-zero with failure artifacts preserved

#### Scenario: Invalid command verdict is not trusted

**Given**: a command adapter returns unparseable JSON or a JSON object that does not match the verdict contract
**When**: `review-gauntlet review` processes the adapter result
**Then**: no finding occurrence is created from that result
**And**: the selected cell is not marked reviewed
**And**: the review command exits non-zero with failure artifacts preserved
