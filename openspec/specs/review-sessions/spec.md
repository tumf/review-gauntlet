### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`. Review universe construction SHALL apply deterministic built-in artifact exclusions and default review-path exclusions before creating review cells. Default review-path exclusions SHALL include `openspec/`, `tests/`, `docs/`, common test-file patterns, and package manager manifest or lock files such as `uv.lock`, `package.json`, `package-lock.json`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `pom.xml`, `Gemfile.lock`, and equivalent dependency metadata files. Review-path exclusions SHALL apply consistently to session review cell creation, review universe file digests, and target digests. Package manager manifest or lock files MAY remain visible in general inventory diagnostics. Review cell ledger identity SHALL be scoped to the owning session, so multiple sessions MAY contain the same deterministic review cell ID without corrupting or blocking each other. `init` SHALL support `--format text|json`, defaulting to `text`, and SHALL NOT expose `--audience` because it only emits a final initialization result.

<!-- Expected canonical result after archive: the review universe requirement documents package manager manifest and lock file exclusions as default review-path exclusions that affect session cells and digests, while inventory diagnostics may still list them. -->

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

#### Scenario: Package files are excluded from default review cells

**Given**: a repository with changed package files such as `uv.lock`, `package.json`, `package-lock.json`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `pom.xml`, and `Gemfile.lock`
**And**: the same repository has a changed source file such as `src/app.py`
**When**: the developer runs `review-gauntlet init --worktree --format json`
**Then**: review cells are created for the changed source file
**And**: no review cell is created for the changed package files

#### Scenario: Full-repository review still excludes package files

**Given**: a repository containing source files and package files such as `uv.lock`, `package-lock.json`, and `Cargo.lock`
**When**: the developer runs `review-gauntlet init --all --format json`
**Then**: review cells are created for eligible source files
**And**: no review cell is created for package manager manifest or lock files

#### Scenario: Package-only changes do not stale review target digest

**Given**: an active moving-target session whose current review universe has no package files
**When**: only package manager manifest or lock files change before a later status or review command
**Then**: those package-only changes are omitted from review universe file digests and the target digest
**And**: no new package-file review cells are added by default

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

The review command SHALL support a positive integer `--concurrency` option, defaulting to `8`, that limits how many selected review cells may execute adapter review work simultaneously within that one run. The concurrency option SHALL NOT change the review budget, selected-cell eligibility, target policy, or the requirement that coverage is recorded only for successfully executed cells.

The review command SHALL support `--format text|json`, defaulting to `text`. For default human-audience runs, the review command SHALL expose review-run and per-cell progress on stderr while adapter work is in progress. Progress output SHALL NOT pollute stdout final output. When `--audience agent` is explicitly selected, the review command SHALL suppress decorative progress because agent callers do not need progress display. If the user interrupts the command, the review command SHALL cancel pending work, terminate in-flight command adapter subprocesses when possible, and leave unfinished cells in a non-reviewed state.

If one or more selected cells fail after other selected cells have completed successfully, the review command SHALL persist coverage, findings, occurrences, and applicable fixed-finding verification for the successful cells before returning a failed command result. Failed cells SHALL remain non-reviewed and visible for later retry.

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

#### Scenario: Partial failure preserves successful coverage

**Given**: an active session where a review run selects multiple cells
**And**: at least one selected cell succeeds
**And**: at least one selected cell fails in the same run
**When**: `review-gauntlet review` finalizes that run
**Then**: every successful selected cell is recorded as reviewed with its findings and occurrences
**And**: the final output reports the number of successful cells persisted in `reviewed_cells`
**And**: the command exits with a failure result that identifies a failed cell
**And**: failed cells remain pending or stale for later retry

#### Scenario: Partial failure verifies only successful paths

**Given**: an active session with fixed findings awaiting verification on two paths
**And**: a review run succeeds for one path and fails for the other path
**When**: `review-gauntlet review` finalizes that partial run
**Then**: fixed-finding verification may update the finding for the successfully evaluated path
**And**: the finding for the failed path remains `fixed_pending_verification`

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

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

#### Scenario: Findings mark filter matches hyphenated public state

**Given**: an active session with a `false_positive` finding
**When**: the developer runs `review-gauntlet findings --all --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list includes that false-positive finding
**And**: no finding state is modified

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

Command adapter configuration validation SHALL reject invalid environment variable names and SHALL define how literal braces are represented in template-bearing strings. Configuration errors SHALL be reported before adapter execution.

#### Scenario: Adapter env keys are validated

**Given**: a command adapter config whose `env` contains an invalid key such as `BAD-NAME` or an empty string
**When**: the review command loads the config
**Then**: the config is rejected with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Template literal brace behavior is explicit

**Given**: a command adapter config string containing a literal brace sequence
**When**: the config is loaded
**Then**: review-gauntlet either accepts the documented literal escaping form or rejects the string with an actionable unsupported-template error
**And**: supported variables such as `{prompt}` continue to validate successfully

### Requirement: Command adapter SHALL invoke external tools safely and preserve artifacts

The command adapter SHALL invoke configured tools without a shell, SHALL expose generated prompts through `{prompt}` argv/env template expansion, SHALL collect verdicts from stdout JSON when explicitly configured or from file JSON by default, and SHALL preserve per-cell artifacts for auditability. In file-json mode, stdout and stderr SHALL be preserved as logs but SHALL NOT be parsed or trusted as verdict input. The generated prompt exposed through `{prompt}` SHALL describe the target file with metadata rather than embedding the target file body.

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
**And**: the expanded prompt identifies the target file using path, digest, byte size, and line count rather than file body text
**And**: the command adapter does not send the prompt through stdin as a transport side effect
**And**: the command adapter does not pass a prompt file as a transport side effect

#### Scenario: Command adapter supports stdout-json output

**Given**: a command adapter configuration explicitly using output mode `stdout-json`
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict emitted to stdout
**And**: non-JSON stdout text remains invalid verdict output

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

### Requirement: CI runtime SHALL be pinned to the project Python version

Repository CI SHALL install the Python runtime declared by project guidance rather than the latest interpreter available to the package manager.

#### Scenario: CI installs Python 3.11

**Given**: the GitHub Actions workflow for repository checks
**When**: CI sets up Python with `uv`
**Then**: the workflow installs Python 3.11 explicitly
**And**: dependency resolution, linting, type checking, and tests run against that runtime
