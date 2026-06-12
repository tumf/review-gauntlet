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

`review-gauntlet review` SHALL create durable run evidence only for review attempts that can evaluate selected cells. A review invocation with no selected current cells SHALL NOT create a run record that can satisfy finalization freshness or reviewed-target evidence.

#### Scenario: Zero-cell review does not refresh finalization evidence

**Given**: an active session whose current cells are already reviewed
**When**: the developer runs `review-gauntlet review --budget 1`
**Then**: no new reviewed-cell coverage is recorded
**And**: no zero-cell run is used as the last reviewed target digest for finalization

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

When the same finding is detected while it is `fixed_pending_verification`, the finding SHALL reopen deterministically and SHALL NOT be immediately verified in the same run that re-detected it.

#### Scenario: Redetected fixed finding remains reopened

**Given**: a finding is `fixed_pending_verification`
**When**: a later review run detects the same finding fingerprint again
**Then**: the finding status becomes `reopened`
**And**: later verification logic in the same run does not transition it to `fixed_verified`

### Requirement: Status and findings commands SHALL expose actionable session state

The CLI SHALL expose current session state without modifying review coverage. `status` SHALL report coverage, finding counts, target freshness, finalization readiness, and the next required action. `findings` SHALL list open findings by default, support showing all findings, and support read-only filtering by finding path and triage mark.

Session commands that emit summaries SHALL use `--format text` for human-readable output and `--format json` for structured output where supported, with `text` as the default. Commands that support decorative progress or audience-specific progress output SHALL support `--audience human|agent` for progress control. Commands that only emit a final result and no intermediate progress UI SHALL NOT expose an `--audience` option.

<!-- Expected canonical result after archive: findings documents repeatable `--path` and `--mark` filters while preserving default terminal suppression, `--all`, `--format text|json`, and rejection of `--audience`. -->

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
**And**: the help output lists `--path`
**And**: the help output lists `--mark`
**And**: the help output does not list `--audience`

#### Scenario: Findings emits structured JSON on request

**Given**: an active session with findings
**When**: the developer runs `review-gauntlet findings --format json`
**Then**: stdout contains parseable JSON for the final findings result

#### Scenario: Findings filters by mark

**Given**: an active session with confirmed, reopened, and false-positive findings
**When**: the developer runs `review-gauntlet findings --mark confirmed --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only confirmed findings
**And**: no finding state is modified

#### Scenario: Findings filters by path

**Given**: an active session with findings in multiple repository paths
**When**: the developer runs `review-gauntlet findings --path src/review_gauntlet/config.py --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only findings for that path
**When**: the developer runs `review-gauntlet findings --path src/review_gauntlet/ --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only findings under that path prefix

#### Scenario: Findings combines path and mark filters

**Given**: an active session with confirmed and reopened findings across multiple paths
**When**: the developer runs `review-gauntlet findings --path src/review_gauntlet/ --mark confirmed --mark reopened --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only confirmed or reopened findings under `src/review_gauntlet/`

#### Scenario: Findings filter respects terminal visibility

**Given**: an active session with a false-positive finding
**When**: the developer runs `review-gauntlet findings --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list omits the false-positive finding
**When**: the developer runs `review-gauntlet findings --all --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list includes the false-positive finding

#### Scenario: Findings rejects obsolete audience and human format options

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --audience agent`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet findings --format human`
**Then**: the command fails with a usage error

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

#### Scenario: Malformed decision metadata blocks finalize without crashing

**Given**: a terminal finding event with malformed JSON metadata or an invalid `until` date
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command returns a structured failure result
**And**: the result includes a blocker for invalid or expired terminal-decision metadata
**And**: no traceback is printed

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
