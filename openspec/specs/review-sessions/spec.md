### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`. Review universe construction SHALL apply deterministic built-in artifact exclusions and default review-path exclusions, including `openspec/`, `tests/`, and `docs/`, before creating review cells.

#### Scenario: Initialize the default workspace diff review session

**Given**: a Git repository with staged changes, unstaged changes, untracked non-ignored files, and unrelated unchanged tracked files
**When**: the developer runs `review-gauntlet init`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records a moving workspace diff target policy
**And**: creates initial review cells only for eligible staged, unstaged, and untracked non-ignored files
**And**: does not create review cells for unrelated unchanged tracked files
**And**: does not create review cells for built-in artifact-excluded paths or default review-path-excluded `openspec/`, `tests/`, `docs/`, test, or generated paths
**And**: does not execute a review run

#### Scenario: Initialize an explicit worktree review session

**Given**: a Git repository with staged changes, unstaged changes, and untracked non-ignored files
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the CLI creates the same workspace diff target policy as default `review-gauntlet init`
**And**: records enough target information for later review runs to detect changed workspace diff content
**And**: applies the same built-in artifact and default review-path exclusions as default workspace diff initialization

#### Scenario: Initialize a branch review session

**Given**: a repository with a valid base reference and head reference
**And**: the head reference changes some eligible files while other tracked files remain unchanged
**When**: the developer runs `review-gauntlet init --from origin/main --to HEAD`
**Then**: the CLI creates durable session state under `.review-gauntlet/`
**And**: records the base reference, head reference, moving head mode, target kind, ruleset digest, and initial review cells
**And**: creates review cells for eligible files changed between the base and head references
**And**: does not create review cells for unrelated unchanged tracked files
**And**: does not create review cells for built-in artifact-excluded paths or default review-path-excluded `openspec/`, `tests/`, `docs/`, test, or generated paths
**And**: does not execute a review run

#### Scenario: Initialize a fixed commit review session

**Given**: a repository with a valid commit object that changes eligible files
**When**: the developer runs `review-gauntlet init --commit abc123`
**Then**: the CLI creates a fixed-target session for that commit
**And**: creates review cells for eligible files changed by that commit
**And**: does not create review cells for built-in artifact-excluded paths or default review-path-excluded `openspec/`, `tests/`, `docs/`, test, or generated paths changed by that commit
**And**: later runs treat the target as immutable unless a new session is initialized

#### Scenario: Initialize a full repository review session

**Given**: a repository with eligible tracked files, eligible untracked non-ignored files, ignored files, review-gauntlet generated state, generated dependency directories, `openspec/`, `tests/`, `docs/`, and conventional test files
**When**: the developer runs `review-gauntlet init --all`
**Then**: the CLI creates a full-repository targeted session
**And**: creates review cells from the existing full inventory rules
**And**: excludes ignored files, built-in generated artifacts, dependency/vendor directories, and `.review-gauntlet/` state
**And**: excludes default review-path `openspec/`, `tests/`, `docs/`, test, and generated patterns from review cells
**And**: does not execute a review run

#### Scenario: Init rejects mixed target scopes

**Given**: a repository
**When**: the developer combines `--all` with `--worktree`, `--commit`, or `--from/--to`
**Then**: the CLI fails with a usage error
**And**: no new review session is created

#### Scenario: Review universe digest ignores excluded paths

**Given**: an active review session whose target contains eligible source files and built-in excluded generated, `openspec/`, `tests/`, `docs/`, or test paths
**When**: an excluded path changes but eligible source files and review rules do not change
**Then**: the review target digest remains stable for coverage reconciliation
**And**: previously reviewed eligible cells are not marked stale only because of the excluded path change

#### Scenario: Eligible source changes still stale review coverage

**Given**: an active review session with reviewed coverage for an eligible source file
**When**: that eligible source file changes
**Then**: the review target digest changes
**And**: affected review cells become stale according to existing reconciliation behavior

### Requirement: Review command SHALL advance exactly one run

`review-gauntlet review` SHALL advance the active session by one review run only. It SHALL recalculate the current review universe according to the active session's target policy, reconcile existing ledger state, review eligible cells within the configured budget, execute review work through the selected review adapter, update cell coverage only for successfully reviewed cells, record findings and occurrences, verify pending fixes when possible, and return the next required action without recursively continuing the session loop. It SHALL NOT accept target selection flags or retarget the active session.

The review command SHALL support a positive integer `--concurrency` option, defaulting to `8`, that limits how many selected review cells may execute adapter review work simultaneously within that one run. The concurrency option SHALL NOT change the review budget, selected-cell eligibility, target policy, or the requirement that coverage is recorded only for successfully executed cells.

#### Scenario: Review advances once with remaining pending work

**Given**: an active session with more pending review cells than the current review budget
**When**: the developer runs `review-gauntlet review`
**Then**: the CLI creates exactly one immutable run record
**And**: reviews only the cells selected for that run
**And**: leaves remaining eligible cells pending
**And**: reports that the next required action is to run review again or triage findings, depending on the run result

#### Scenario: Review rejects target selection flags

**Given**: an active session
**When**: the developer runs `review-gauntlet review --from main --to HEAD`, `review-gauntlet review --commit abc123`, `review-gauntlet review --worktree`, or `review-gauntlet review --all`
**Then**: argument parsing fails with a usage error
**And**: the active session target policy is not changed
**And**: no review run is created

#### Scenario: Review executes selected cells with bounded concurrency

**Given**: an active session with multiple eligible pending review cells
**And**: the current review budget permits multiple cells in the run
**When**: the developer runs `review-gauntlet review --concurrency 2`
**Then**: the CLI creates exactly one immutable run record
**And**: selects eligible cells deterministically up to the configured budget
**And**: executes adapter review work for no more than two selected cells at the same time
**And**: applies findings, occurrences, and cell coverage updates deterministically for successfully reviewed cells

#### Scenario: Review rejects invalid concurrency

**Given**: an active session
**When**: the developer runs `review-gauntlet review --concurrency 0`
**Then**: argument handling fails with a usage error
**And**: no adapter review work is executed
**And**: no cell is marked reviewed because of that command

#### Scenario: Concurrent review preserves budget semantics

**Given**: an active session with more eligible review cells than the current review budget
**When**: the developer runs `review-gauntlet review --budget 1 --concurrency 8`
**Then**: the CLI selects at most one cell for that run
**And**: reviews at most one cell even though the concurrency limit is higher than the budget
**And**: leaves remaining eligible cells pending

#### Scenario: Concurrent review preserves failed-cell visibility

**Given**: an active session with multiple selected review cells
**And**: the selected review adapter fails for one selected cell
**When**: the developer runs `review-gauntlet review --concurrency 2 --format json`
**Then**: the CLI exits non-zero and reports the failed cell id, error, failure details, and current session status
**And**: the failed cell is not marked reviewed
**And**: successful cells whose results were committed are recorded explicitly in coverage and findings state

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

Session commands that emit summaries SHALL use `--format json` for structured output and SHALL support `--audience agent` for automation-safe output aligned with OCR review conventions. `--audience agent` SHALL suppress progress UI and decorative human output.

#### Scenario: Status reports next action

**Given**: an active session with reviewed cells and untriaged findings
**When**: the developer runs `review-gauntlet status --format json --audience agent`
**Then**: the JSON output includes `session_id`, `session_state`, coverage counts, finding state counts, `can_finalize`, and `next_required_action`
**And**: `next_required_action` is `triage_findings`

#### Scenario: Agent audience suppresses decorative output

**Given**: an active session
**When**: the developer runs `review-gauntlet status --format json --audience agent`
**Then**: stdout contains only parseable JSON for the final status result
**And**: stdout does not include progress bars, spinners, markdown headings, or explanatory prose

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

The new session workflow SHALL preserve the existing `inventory`, `plan`, and `report` command contracts while reusing their concepts for review-universe generation. Inventory generation SHALL exclude review-gauntlet-generated session state, common cache/build/editor artifacts, and files ignored by Git when Git-backed discovery is available, so coverage reflects the project review target rather than generated tool state.

#### Scenario: Existing inventory JSON remains parseable

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Existing report remains available

**Given**: a repository with files to review
**When**: the developer runs `review-gauntlet report <root>`
**Then**: the command emits the markdown review matrix report
**And**: existing tests for report output continue to pass

#### Scenario: Generated review state is excluded from inventory

**Given**: a repository containing `.review-gauntlet/` session state and run artifacts
**When**: the developer runs `review-gauntlet inventory <root> --json`
**Then**: no path under `.review-gauntlet/` appears in the inventory output
**And**: generated review state does not create review cells for subsequent session reconciliation

#### Scenario: Common generated artifacts are excluded from fallback inventory

**Given**: a project tree with normal source files and generated artifacts under cache, build, coverage, virtualenv, or editor metadata paths
**And**: Git-backed discovery is unavailable
**When**: review-gauntlet builds inventory by recursively walking the filesystem
**Then**: normal source files remain included
**And**: generated artifact paths such as `.ruff_cache/`, `.pyright/`, `.mypy_cache/`, `build/`, `dist/`, `wheels/`, `*.egg-info/`, `.coverage`, `htmlcov/`, `.DS_Store`, `.idea/`, and `.vscode/` are excluded

#### Scenario: Git-backed inventory applies built-in exclusions

**Given**: Git-backed discovery returns untracked files that are not ignored by Git
**And**: some of those paths are under review-gauntlet built-in excluded directories
**When**: review-gauntlet builds inventory from Git output
**Then**: built-in excluded paths are filtered out before classification
**And**: legitimate tracked or untracked project files outside built-in exclusions remain eligible for classification

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
