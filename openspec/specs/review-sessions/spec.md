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

`review-gauntlet review` SHALL execute Phase 1: reviewing all pending review cells in a single invocation. A review invocation with no pending cells SHALL NOT create a run record. `review-gauntlet review` SHALL return structured failed-cell output when any adapter invocation fails. Successful cells from the same run SHALL still persist coverage and findings before the command exits, including successful cells completed before or during handling of a user interrupt.

When `review-gauntlet review` is interrupted by the user, the command SHALL exit with status code `130` and SHALL NOT output a raw Python traceback. If `--format json` is used, stdout SHALL contain parseable JSON that includes `interrupted: true`. The active session SHALL remain available for retry after interruption.

#### Scenario: Zero-cell review does not create run record

**Given**: an active session whose current cells are already reviewed
**When**: the developer runs `review-gauntlet review`
**Then**: no new reviewed-cell coverage is recorded
**And**: no run record is created

#### Scenario: Partial adapter failure preserves successful cells

**Given**: a review run with 3 pending cells
**And**: one adapter invocation fails
**When**: the run completes
**Then**: successful cells are recorded as reviewed
**And**: findings from successful cells are persisted
**And**: the failed cell remains pending for retry

#### Scenario: Interrupted review preserves completed cells

**Given**: a review run with 3 pending cells
**And**: one cell adapter invocation has completed successfully before the user interrupt is handled
**When**: the developer interrupts `review-gauntlet review`
**Then**: the completed cell is recorded as reviewed
**And**: findings from the completed cell are persisted for the current run
**And**: cells that did not complete successfully remain pending for retry
**And**: the active session remains available for subsequent review commands

#### Scenario: Interrupted review drains already completed futures

**Given**: a parallel review run with multiple in-flight cell futures
**And**: future A is complete, future B is still running, and future C has not completed
**When**: interrupt handling begins
**Then**: future A is collected without waiting for future B or C
**And**: a successful outcome from future A is persisted as reviewed coverage
**And**: futures B and C are cancelled or left pending without being marked reviewed

#### Scenario: Interrupted review exits without traceback

**Given**: `review-gauntlet review` is executing with pending cells
**When**: the user interrupts with `Ctrl-C`
**Then**: the command exits with status code `130`
**And**: stderr does not contain `Traceback`
**And**: stderr does not contain an uncaught `KeyboardInterrupt` stack trace

#### Scenario: Interrupted review emits structured JSON output

**Given**: `review-gauntlet review --format json` is executing
**When**: the user interrupts with `Ctrl-C`
**Then**: stdout is parseable JSON
**And**: the JSON object includes `"interrupted": true`
**And**: the JSON object includes `run_id`, `reviewed_cells`, and standard status fields

#### Scenario: Active session survives interrupt for retry

**Given**: a review run is interrupted after adapter cancellation and result persistence
**When**: the developer checks session state
**Then**: the active session remains available
**And**: the developer can run `review-gauntlet review` again without re-initialization

<!-- Expected canonical result after archive: the review command requirement explicitly covers preserving completed cell coverage and findings during user interruption, structured interrupt exit with code 130, no traceback, parseable JSON with interrupted flag, and active session preservation. -->

### Requirement: Review rules and prompts SHALL port the pinned OCR corpus

The default review logic SHALL derive its bundled prompts, path-based rules, and line-level review comment contract from Alibaba `open-code-review` commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`. The ported corpus SHALL include OCR's system rule map and all built-in rule documents, SHALL be usable without network access, and SHALL be included in the ruleset digest for stale-coverage detection. Review execution adapters SHALL use this OCR-derived prompt and verdict contract when asking external tools to review cells.

Generated review prompts SHALL identify the target file by repository root, repository-relative file path, content digest, file size in bytes, and line count. Generated prompts SHALL NOT embed the target file body directly. External review tools that need source content SHALL read the target file from the repository working tree path.

The bundled rule corpus SHALL include a local Solidity rule document selected for `.sol` files. Solidity guidance SHALL cover smart-contract-specific review risks across these required categories: specification and assumptions; Solidity version and compiler settings; access control; reentrancy and external calls; ETH and token transfers; input validation and boundary values; numeric calculation, rounding, and casting; state management and invariants; randomness, time, block data, and on-chain secrecy assumptions; oracle, pricing, and external data; gas and denial-of-service resistance; upgradeable/proxy contracts; signatures, permits, and replay protection; ERC/interface compliance; emergency design; events and auditability; testing and verification; deployment and operations; code quality and readability; and high-risk signal review. The guidance SHALL also include the practical review order of checking specification/invariants, permissions/funds, external calls/reentrancy, accounting/math, high-risk mechanisms, boundary/DoS/gas/error cases, and tests/static analysis/deployment settings.

#### Scenario: OCR rule corpus is bundled and traceable

**Given**: the installed `review-gauntlet` package
**When**: the review ruleset is loaded
**Then**: the ruleset records upstream repository `https://github.com/alibaba/open-code-review`
**And**: records upstream commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`
**And**: exposes the default OCR rule map and all OCR rule documents as local package data
**And**: exposes the bundled Solidity rule document as local package data
**And**: the Solidity rule document covers the required 20-category smart-contract review checklist and practical review order

#### Scenario: OCR path rule mapping is preserved

**Given**: files named `pom.xml`, `package.json`, `Cargo.toml`, `src/app.ts`, `src/main.rs`, `src/main.c`, `contracts/Vault.sol`, and `README.md`
**When**: the default ruleset selects review rules for those paths
**Then**: the selected rule documents match OCR's pinned system rule map plus the bundled Solidity rule mapping
**And**: `contracts/Vault.sol` selects `solidity.md`
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

#### Scenario: External command receives OCR-derived review prompt without commit reference

**Given**: a selected review cell with a file path, content digest, byte size, line count, and rule id
**And**: the session is configured to use an external command adapter
**When**: `review-gauntlet review` invokes the adapter
**Then**: the generated prompt includes the selected OCR-derived rule guidance
**And**: the prompt identifies the file and review cell being evaluated
**And**: the prompt includes the target file path, content digest, byte size, and line count
**And**: the prompt does not include a review commit SHA
**And**: the prompt does not embed the target file body
**And**: the prompt instructs the external command to read the target file from the repository working tree path when content is needed
**And**: the prompt instructs the external command to return the OCR-style verdict JSON contract

### Requirement: Review cells SHALL model coverage independently from finding state

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows. Review cells SHALL transition only from `PENDING` to `REVIEWED`. The `STALE` and `SUPERSEDED` states are removed. File content changes between session initialization and review SHALL NOT trigger automatic state transitions on existing cells.

#### Scenario: Unknown review cell update fails

**Given**: a session ledger without cell `RGC-missing`
**When**: internal reconciliation attempts to update `RGC-missing`
**Then**: the store raises an actionable lookup error
**And**: no caller can treat the missing cell as updated coverage

#### Scenario: Review cell transitions are PENDING to REVIEWED only

**Given**: an active session with a pending review cell
**When**: the cell is successfully reviewed
**Then**: the cell state is `REVIEWED`
**And**: no other state transitions are possible for the cell

### Requirement: Findings SHALL use stable session-level identity

Finding ID allocation SHALL be deterministic and monotonic within a session. New IDs SHALL NOT be based on the current finding row count because row gaps from migration, repair, or deletion can otherwise reuse an existing human-readable ID.

#### Scenario: Finding id allocation does not reuse gaps

**Given**: a session with existing findings `RGF-0001` and `RGF-0003`
**When**: a new distinct finding is recorded
**Then**: the new finding ID is `RGF-0004`
**And**: no existing finding ID is reused

### Requirement: Finding triage SHALL be explicit and event-backed

Finding triage SHALL transition findings from `open` to either `confirmed` (real finding handled by the resolution phase) or `dismissed` (not a valid issue or intentionally closed as a non-issue). Triage event metadata SHALL be validated before persistence. Dismissed findings SHALL include a `dismiss_reason`. Both `confirmed` and `dismissed` are terminal states.

Resolve-phase ready prompts SHALL describe the allowed transition targets for the current finding state before asking an external agent to write a resolution verdict. For `open` findings, the prompt SHALL instruct agents to use only `confirmed` or `dismissed`, and SHALL explain that false positives and other non-issues are represented as `dismissed` with a durable reason.

Turn verdict validation SHALL reject invalid requested finding transitions before persistence and SHALL report the finding ID, current state, requested state, and allowed target states.

#### Scenario: Open finding prompt lists only valid resolution states

**Given**: an active session with an `open` finding
**When**: `review-gauntlet run` builds a resolve ready prompt for that finding
**Then**: the prompt lists `confirmed` and `dismissed` as the allowed target states
**And**: the prompt does not instruct the agent to mark the open finding directly as `false_positive`, `accepted_risk`, `waived`, `fixed_pending_verification`, or `fixed_verified`

#### Scenario: False positive open finding is represented as dismissed

**Given**: an active session with an `open` finding
**When**: the resolution agent determines the finding is a false positive
**Then**: the prompt instructs the agent to emit a `dismissed` resolution
**And**: the prompt requires a durable `dismiss_reason`

#### Scenario: Invalid transition verdict is actionable

**Given**: an active session with finding `RGF-1020` in state `open`
**And**: a turn verdict requests state `false_positive` for `RGF-1020`
**When**: Review Gauntlet validates the turn verdict against the active session
**Then**: validation fails before the finding state is persisted
**And**: the diagnostic names `RGF-1020`, `open`, `false_positive`, and the allowed target states `confirmed` and `dismissed`

### Requirement: Status and findings commands SHALL expose actionable session state

Status and findings commands SHALL reflect the simplified two-phase model. Finding state counts SHALL use `open`, `confirmed`, `dismissed`. Cell state counts SHALL use `pending`, `reviewed`. Stale-related state displays are removed.

#### Scenario: Status shows two-phase state

**Given**: an active session with 3 pending cells, 5 reviewed cells, 2 open findings, 1 confirmed finding
**When**: the developer runs `review-gauntlet status --format json`
**Then**: coverage shows `pending: 3`, `reviewed: 5`
**And**: findings show `open: 2`, `confirmed: 1`, `dismissed: 0`

### Requirement: Finalize SHALL validate completion without running review work

Finalize SHALL require all cells to be `REVIEWED` and all findings to be `confirmed` or `dismissed`. Finalize SHALL NOT require separate verification of fixed findings since the resolution agent handles verification as part of the `confirmed` determination.

#### Scenario: Successful finalize with two-phase completion

**Given**: an active review session with all cells `REVIEWED`
**And**: all findings are `confirmed` or `dismissed`
**And**: review-universe files are clean relative to `HEAD`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: `.review-gauntlet/checkpoints/latest/status.json` is written
**And**: stdout contains parseable JSON listing the generated files
**And**: the result includes `checkpoint_state: complete`

#### Scenario: Open findings block finalize

**Given**: an active review session with all cells reviewed
**And**: at least one finding is `open`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with structured blockers
**And**: blockers indicate open findings remain
**And**: no checkpoint files are written

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

Command adapter configuration SHALL provide bounded execution defaults for autonomous agents. `adapter.timeout_seconds` SHALL default to 3600 seconds when not explicitly configured. `adapter.quiet_timeout_seconds` SHALL default to 600 seconds when not explicitly configured. Both timeout fields SHALL reject non-finite or non-positive values before adapter execution.

<!-- Expected canonical result after archive: command adapter configuration documents default overall timeout as 3600 seconds and default quiet timeout as 600 seconds, with validation requirements for both fields. -->

#### Scenario: Default adapter timeouts are applied

**Given**: a valid command adapter configuration omits `timeout_seconds` and `quiet_timeout_seconds`
**When**: Review Gauntlet loads the effective configuration
**Then**: `adapter.timeout_seconds` is `3600.0`
**And**: `adapter.quiet_timeout_seconds` is `600.0`

#### Scenario: Explicit adapter timeouts override defaults

**Given**: a valid command adapter configuration explicitly sets `timeout_seconds` and `quiet_timeout_seconds`
**When**: Review Gauntlet loads the effective configuration
**Then**: the configured timeout values are preserved
**And**: default timeout values do not override the explicit values

#### Scenario: Invalid quiet timeout fails validation before execution

**Given**: a command adapter configuration whose `quiet_timeout_seconds` value is zero, negative, NaN, or infinite
**When**: `review-gauntlet config validate` or an adapter-backed command loads that configuration
**Then**: configuration validation fails with an actionable error
**And**: no external adapter command is executed

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

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL include eligible files changed from that checkpoint's `review_base_commit` to `HEAD` and SHALL also include current eligible uncommitted worktree changes: staged, unstaged, and untracked non-ignored files. If no latest checkpoint exists, the default target SHALL be an all-files review over the current eligible review inventory. If a latest checkpoint exists but is invalid or unusable, initialization SHALL fail with the checkpoint validation error instead of falling back to all-files review. The `--worktree` flag remains an explicit request for worktree-only review; callers that need committed changes without uncommitted worktree changes SHALL use `--commit` or `--from/--to`.

#### Scenario: Init creates an active session without starting a run

**Given**: a repository with eligible review files
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: the session ledger contains the initialized review cells
**And**: no review run row is created for the session
**And**: stdout includes `session_state: active`, `run_count: 0`, and a lifecycle field showing that no run has started
**And**: stdout identifies `review-gauntlet review` as the next command for starting review execution

#### Scenario: Init with no review cells does not suggest review

**Given**: a repository target whose selected files are all excluded from review cells
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: stdout reports `cell_count: 0`, `run_count: 0`, and `run_state: none`
**And**: stdout does not identify `review-gauntlet review` as `next_command`
**And**: no review run row is created for the session

#### Scenario: Worktree flag is accepted

**Given**: an installed `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the session target is a WORKTREE kind reviewing uncommitted changes
**And**: the command exits successfully

#### Scenario: Init with no flags and no checkpoint defaults to all-files review

**Given**: a repository with no latest checkpoint
**And**: the repository has eligible unchanged tracked files and eligible uncommitted files
**When**: the developer runs `review-gauntlet init` without target flags
**Then**: the session target is ALL kind
**And**: review cells cover the eligible current review inventory, including unchanged tracked files and eligible uncommitted files

#### Scenario: Init with latest checkpoint includes uncommitted worktree changes

**Given**: a repository with a usable latest checkpoint whose `review_base_commit` is an ancestor of `HEAD`
**And**: there are eligible files changed between the checkpoint base and `HEAD`
**And**: there are eligible staged, unstaged, and untracked non-ignored worktree files
**When**: the developer runs `review-gauntlet init` without target flags
**Then**: the session target records the checkpoint base and `HEAD` as the committed review range
**And**: the session target records that worktree changes are included
**And**: review cells cover the union of eligible checkpoint-base-to-HEAD files and eligible staged, unstaged, and untracked worktree files

#### Scenario: Explicit branch init excludes uncommitted worktree changes

**Given**: a repository with a valid base reference and head reference
**And**: there are eligible uncommitted worktree files outside that committed range
**When**: the developer runs `review-gauntlet init --from <base> --to <head>`
**Then**: the session target is BRANCH kind without worktree inclusion
**And**: review cells cover eligible files changed between the base and head references
**And**: review cells do not include the unrelated uncommitted worktree files

### Requirement: Ready command SHALL emit the next skill-directed prompt

`review-gauntlet ready` SHALL emit the next skill-directed prompt from concrete renderable work items. It SHALL preserve deterministic priority: pending review cells, then open findings, then finalize readiness. Stale review cells are removed; no stale-related prompts are generated.

#### Scenario: Ready priority uses new two-phase order

**Given**: an active session with pending review cells and open findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the prompt targets pending review cells (Phase 1)
**And**: open findings are not selected while pending cells exist

#### Scenario: Ready selects open findings after all cells reviewed

**Given**: an active session with all cells reviewed and open findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the prompt targets open findings (Phase 2)

#### Scenario: Ready selects finalize when both phases complete

**Given**: an active session with all cells reviewed and all findings terminal
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the prompt is the finalize prompt

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

### Requirement: Run agent failures SHALL display distinct failure reasons

`review-gauntlet run` SHALL preserve and display distinct external-agent and orchestration failure reasons instead of collapsing them into misleading timeout or generic failure labels. Timeout wording SHALL be reserved for actual timeout failures, and configured timeout details SHALL be rendered concisely without duplicated or unset wording.

Quiet timeout caused by lack of stdout/stderr output SHALL remain distinguishable from overall wall-clock command timeout in structured run results and artifacts, while human-facing terminal TUI wording MAY present both as timeout-family failures.

<!-- Expected canonical result after archive: run failure semantics distinguish `quiet_timeout` from overall `timeout` while preserving timeout-family terminal display. -->

#### Scenario: Quiet timeout remains distinct from overall command timeout

**Given**: a configured command adapter subprocess is still running
**And**: the subprocess has produced no stdout or stderr output for `adapter.quiet_timeout_seconds`
**And**: the overall `adapter.timeout_seconds` deadline has not been reached
**When**: `review-gauntlet run` enforces adapter timeouts
**Then**: the subprocess is terminated
**And**: the run result or persisted command artifact reports `reason` as `quiet_timeout`
**And**: the diagnostic includes the configured `quiet_timeout_seconds`
**And**: the diagnostic remains distinguishable from an overall `timeout` failure

#### Scenario: Overall timeout remains distinct

**Given**: a configured command adapter subprocess remains running until `adapter.timeout_seconds` elapses
**When**: `review-gauntlet run` enforces adapter timeouts
**Then**: the subprocess is terminated
**And**: the run result or persisted command artifact reports `reason` as `timeout`
**And**: the diagnostic includes the configured `timeout_seconds`
**And**: the failure is not reported as `quiet_timeout` unless the quiet-output deadline was the cause

#### Scenario: Quiet timeout renders as terminal timeout family in TUI

**Given**: a run step fails because of quiet timeout
**When**: the run TUI renders the result
**Then**: the agent is displayed as a terminal timeout-family failure
**And**: the display does not label the failure as command failed, startup error, interrupted, or max steps exhausted
**And**: timeout wording is concise and does not duplicate labels such as `timeout timeout`

#### Scenario: Timeout failure remains distinct

**Given**: a configured command adapter times out during `review-gauntlet run`
**When**: the run result or TUI is rendered
**Then**: the agent status is displayed as timed out
**And**: the display includes the effective timeout duration when available
**And**: the display does not include duplicated wording such as `timeout timeout`

#### Scenario: Command non-zero exit is not displayed as timeout

**Given**: a configured command adapter exits non-zero without timing out
**When**: the run result or TUI is rendered
**Then**: the agent status is displayed as command failed or equivalent non-timeout failure wording
**And**: the display does not label the failure as timed out
**And**: stdout or stderr tail evidence remains available for diagnosis

#### Scenario: Startup error is displayed separately

**Given**: a configured command adapter command cannot be started because the executable is missing
**When**: the run result or TUI is rendered
**Then**: the agent status is displayed as startup error or equivalent wording
**And**: the display does not label the failure as timed out or command non-zero exit

#### Scenario: Template error is displayed separately

**Given**: a configured command adapter has an invalid template or cwd expansion
**When**: `review-gauntlet run` prepares the command adapter step
**Then**: the run result reports a template or configuration error
**And**: no external adapter command is executed
**And**: the TUI does not label the failure as timed out

#### Scenario: Interrupted run is displayed separately

**Given**: a run is interrupted by the user or controller
**When**: the run result or TUI is rendered
**Then**: the status is displayed as interrupted
**And**: the display does not label the interruption as failed command execution or timeout

#### Scenario: Max steps exhaustion is displayed separately

**Given**: `review-gauntlet run` reaches its configured maximum number of ready-prompt executions while the active session remains unfinished
**When**: the run result or TUI is rendered
**Then**: the status is displayed as max steps exhausted or equivalent orchestration wording
**And**: the display does not label the condition as an agent timeout

#### Scenario: Ready-to-finalize timeout recovery remains visible

**Given**: an external command adapter times out while the active session has `can_finalize=true` and no finalize blockers
**When**: the run TUI renders the finalize checklist
**Then**: the TUI preserves the manual-finalize recovery cue
**And**: the timeout remains visible as the agent lifecycle reason
**And**: coverage, finding triage, fix verification, and final checks are not shown as failed solely because the adapter timed out

### Requirement: Run agent liveness SHALL reflect actual output activity

`review-gauntlet run` SHALL track agent subprocess stdout and stderr output as it is produced, not only after the subprocess exits. The agent liveness status SHALL reflect the time since the most recent output line, not the time since the subprocess was started. An agent that is actively producing output SHALL be displayed as "running", not "quiet". The Activity panel SHALL show live output tail entries during agent execution.

Output activity SHALL also reset quiet-timeout enforcement. stdout and stderr output lines SHALL both count as liveness. When no output has ever been produced for a running subprocess, quiet-timeout elapsed time SHALL be measured from the agent step start time.

Continuation verdict file detection SHALL be a separate liveness/completion signal for continuation-aware run turns. A valid verdict file MAY start a verdict grace period and terminate a lingering child before quiet timeout, but it SHALL NOT be treated as stdout/stderr output for the purpose of hiding actual output silence. The verdict grace period SHALL be configurable via `adapter.verdict_grace_seconds` and SHALL default to 30 seconds when not explicitly configured.

#### Scenario: Periodic output prevents quiet timeout

**Given**: a configured command adapter subprocess runs longer than `adapter.quiet_timeout_seconds`
**And**: the subprocess produces stdout or stderr output before each quiet-timeout window elapses
**When**: `review-gauntlet run` enforces adapter timeouts
**Then**: the subprocess is not terminated for quiet timeout
**And**: run completion remains governed by process exit or the overall `adapter.timeout_seconds`

#### Scenario: No initial output can quiet-timeout

**Given**: a configured command adapter subprocess starts successfully
**And**: the subprocess produces no stdout or stderr output after start
**When**: `adapter.quiet_timeout_seconds` elapses before the overall timeout
**Then**: `review-gauntlet run` terminates the subprocess for quiet timeout
**And**: `last_output_age_seconds` or equivalent diagnostics reflect silence since step start when available

#### Scenario: Verdict file finalization is distinct from output liveness

**Given**: a continuation-aware finding turn writes a valid continuation JSON file before producing any further stdout or stderr
**When**: `review-gauntlet run` detects the verdict file
**Then**: the run may start the verdict grace period
**And**: the agent lifecycle still reports output age based on stdout/stderr activity
**And**: the final run reason distinguishes verdict-finalized completion from quiet timeout

### Requirement: Ready task prompts SHALL be file-scoped workflows

`review-gauntlet ready` SHALL return a concrete file-scoped task prompt when review cells or findings require action. `review-gauntlet run` SHALL pass that same prompt to the external agent. The prompt SHALL identify one target file and instruct the agent to process that file through triage, optional fix, and marking steps instead of issuing broad state-category instructions such as "triage all untriaged findings" or "review all pending cells."

#### Scenario: Pending review work returns file-scoped task

**Given**: an active session has pending review cells for multiple files
**When**: the developer runs `review-gauntlet ready`
**Then**: the prompt identifies exactly one target `file_path`
**And**: the prompt lists the actionable review cells for that file
**And**: the prompt instructs the agent to review, triage any findings, fix if needed, and mark findings for that file
**And**: the prompt does not instruct the agent to process all pending cells across the session.

#### Scenario: Findings return file-scoped triage-fix-mark task

**Given**: an active session has untriaged, reopened, confirmed, or fixed-pending findings across multiple files
**When**: the developer runs `review-gauntlet ready`
**Then**: the prompt identifies exactly one target `file_path`
**And**: the prompt lists the relevant finding IDs for that file
**And**: the prompt instructs the agent to triage, fix if needed, and mark those findings
**And**: the prompt does not instruct the agent to sweep findings in other files.

#### Scenario: Run uses same file-scoped task

**Given**: `review-gauntlet ready` would return a file-scoped prompt for `src/foo.py`
**When**: the developer runs `review-gauntlet run`
**Then**: the external agent receives the same file-scoped task prompt
**And**: one run step is scoped to that file's workflow.

### Requirement: Run command SHALL preserve primary failure diagnostics

`review-gauntlet run` SHALL not mask a primary ready-prompt, controller, or adapter orchestration failure with a secondary result-handling error. If a run attempt cannot produce the normal result dictionary, command handling SHALL either emit a structured failure result when safe or propagate the original exception without replacing it with an unrelated `NoneType` or missing-key error.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require run command failure handling to preserve the original failure cause and avoid secondary result-shape crashes. -->

#### Scenario: Run does not mask ready failure with none result access

**Given**: an active review session where ready-prompt generation raises an unexpected exception before a run result is produced
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the command does not raise `TypeError: 'NoneType' object is not subscriptable`
**And**: the visible failure preserves the original ready-prompt or controller failure cause
**And**: the command does not report successful completion

### Requirement: Review Gauntlet SHALL NOT operate Git linked worktrees

Review Gauntlet SHALL NOT create, remove, merge, or otherwise mutate Git linked worktrees as part of its session lifecycle. The CLI SHALL NOT accept `--git-worktree`, `--no-setup`, or `--merge` flags. `--worktree` remains exclusively a target-selection flag meaning "review the workspace diff".

Session metadata and agent execution SHALL NOT interpret any `git_worktree` metadata key. If stale `git_worktree` metadata exists from a pre-removal session, Review Gauntlet SHALL proceed using the base repository root and SHALL NOT trigger any linked-worktree behavior.

#### Scenario: Init without --git-worktree records no worktree metadata

**Given**: a developer in a Git repository
**When**: they run `review-gauntlet init --all --format json`
**Then**: the JSON output does not include a `git_worktree` key
**And**: the persisted session metadata does not include a `git_worktree` key

#### Scenario: Init rejects unknown --git-worktree flag

**Given**: a developer in a Git repository
**When**: they run `review-gauntlet init --git-worktree`
**Then**: the command exits with usage error (exit code 64)

#### Scenario: Finalize rejects unknown --merge flag

**Given**: a developer in a Git repository
**When**: they run `review-gauntlet finalize --merge`
**Then**: the command exits with usage error (exit code 64)

#### Scenario: Run ignores stale git_worktree metadata

**Given**: an active session whose metadata was created before `--git-worktree` removal and contains `git_worktree.enabled: true` with a `worktree_path`
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the agent execution root is the base repository root
**And**: no attempt is made to resolve or validate a linked worktree path
**And**: no `worktree_error` reason is emitted

### Requirement: Run TUI SHALL align Agent and Session summary panel heights

`review-gauntlet run` TUI SHALL render the side-by-side Agent and Session summary panel boxes at equal height within the summary row, even when one panel has more rows of content than the other. The equal-height behavior SHALL be scoped to the Agent/Session summary pair and SHALL NOT force unrelated dashboard panels to adopt the same sizing rule.

#### Scenario: Summary panels remain equal height when Agent has artifact row

**Given**: the run TUI renders the Agent and Session summary panels side by side
**And**: the Agent summary includes an optional artifact row
**When**: the summary row is laid out
**Then**: the Agent panel box height equals the Session panel box height
**And**: both panels continue to share equal horizontal width

#### Scenario: Equal-height rule is scoped to summary pair

**Given**: the run TUI renders the header, finalize checklist, Agent panel, Session panel, Activity panel, and footer
**When**: the dashboard CSS/layout is applied
**Then**: equal-height stretching applies to the Agent and Session panel containers
**And**: the common panel style does not force the finalize checklist or Activity panel to use the summary-pair sizing behavior

### Requirement: Run TUI SHALL display title and version in the header border

`review-gauntlet run` SHALL render the interactive TUI top header title as the `#session_header` border title. The border title SHALL include the Review Gauntlet brand marker, product name, and current package version sourced from the package version metadata. The TUI header body SHALL remain focused on run status and metadata, while non-TUI compact/text rendering SHALL remain self-describing with title, status, and metadata text.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI top header to use a versioned border title instead of rendering the product title as ordinary header body content. -->

#### Scenario: TUI header uses versioned border title

**Given**: `review-gauntlet run` selects the interactive TUI path
**When**: the TUI application is constructed
**Then**: the top `#session_header` panel has a border title containing the brand marker, `Review Gauntlet`, and the current package version
**And**: the header body does not render the title as a separate first-line body widget
**And**: the header body still renders run status and metadata

#### Scenario: Version comes from package metadata

**Given**: the package exposes `review_gauntlet.__about__.__version__`
**When**: the run TUI header title is rendered
**Then**: the version shown in the header title matches the package version metadata
**And**: changing the package version source changes the displayed TUI title version without editing a duplicate literal in the TUI title implementation

#### Scenario: Compact text output remains self-describing

**Given**: run dashboard text is rendered outside the interactive TUI border-title context
**When**: compact or fallback dashboard text is generated
**Then**: the text output includes the title, status, and metadata lines
**And**: the output remains readable without relying on a graphical border title

### Requirement: Run TUI SHALL use an explicit dark background

`review-gauntlet run` SHALL render the interactive TUI with an explicitly dark dashboard background rather than relying on Textual default backgrounds. The dark styling SHALL cover the screen and the primary dashboard surfaces while preserving existing brand accents, semantic status colors, panel titles, layout, and run behavior.

#### Scenario: Run TUI renders dark dashboard surfaces

**Given**: `review-gauntlet run` selects the interactive TUI path
**When**: the TUI application is constructed
**Then**: the Textual CSS defines an explicit dark background for the screen
**And**: the header, panel, body, and controls surfaces use dark-compatible background styling
**And**: the existing brand accent and semantic status colors remain available

#### Scenario: Dark styling does not change non-TUI behavior

**Given**: `review-gauntlet run` is executed with JSON output or with TUI disabled
**When**: the run result is rendered
**Then**: output selection and non-TUI rendering behavior remain unchanged
**And**: run controller state, session state, findings state, and finalization behavior are not modified by the dark TUI styling

### Requirement: Run TUI SHALL display actionable finding counts

`review-gauntlet run` TUI SHALL derive visible open finding counts from actionable live finding states instead of requiring an `open` aggregate key in status output. The displayed open count SHALL equal the sum of `reopened`, `untriaged`, `confirmed`, and `fixed_pending_verification`. When the derived open count is non-zero, the Session panel SHALL include a concise action breakdown for triage, fix, and verify work.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require run TUI findings summaries to expose actionable live finding work from state counts, preventing hidden incomplete finding state when no `open` aggregate exists. -->

#### Scenario: TUI derives open findings from actionable state counts

**Given**: an active run snapshot whose finding state counts include untriaged, confirmed, reopened, or fixed-pending verification findings
**And**: the finding state counts do not include an `open` key
**When**: the run TUI renders the Session panel
**Then**: the displayed findings summary includes an open count equal to the sum of those actionable states
**And**: the summary does not display `open 0` while actionable findings exist

#### Scenario: TUI shows action-oriented finding breakdown

**Given**: an active run snapshot with actionable findings requiring triage, fixing, or verification
**When**: the run TUI renders the Session panel
**Then**: the findings summary includes the derived open count
**And**: the summary distinguishes triage work from confirmed-fix work and fixed-pending verification work

#### Scenario: TUI preserves clear state when no actionable findings exist

**Given**: an active run snapshot with no reopened, untriaged, confirmed, or fixed-pending verification findings
**When**: the run TUI renders the Session panel and findings detail text
**Then**: the displayed open finding count is `0`
**And**: the TUI does not invent triage, fix, or verification work

### Requirement: Run TUI SHALL flash-highlight only changed display values

`review-gauntlet run` interactive TUI SHALL make meaningful display updates visible by temporarily flash-highlighting only the changed value or narrowest practical semantic display fragment. The highlight SHALL NOT expand to the entire containing panel when a smaller changed value can be identified. This visual behavior SHALL be limited to the TUI render path and SHALL NOT change non-TUI text output, JSON output, run controller state, session state, finding state, or finalization behavior.

#### Scenario: Coverage completed count highlights without panel-wide flash

**Given**: the run TUI has rendered a Session summary showing coverage `0 / 2`
**When**: the next TUI refresh renders coverage `1 / 2`
**Then**: the changed completed-count value is flash-highlighted
**And**: the unchanged total value is not flash-highlighted solely because the completed count changed
**And**: the containing Session panel is not flash-highlighted as a whole

#### Scenario: Agent step highlights only the changed value

**Given**: the run TUI has rendered `Agent step 1`
**When**: the next TUI refresh renders `Agent step 2`
**Then**: the displayed step value `2` is flash-highlighted
**And**: the entire Agent or Session panel is not flash-highlighted solely because the step value changed

#### Scenario: Finding counts highlight only changed counts

**Given**: the run TUI has rendered a finding summary with zero actionable open findings
**When**: the next TUI refresh renders a non-zero actionable finding count
**Then**: the changed finding count or narrowest practical count fragment is flash-highlighted
**And**: unchanged summary labels are not flash-highlighted solely because the count changed

#### Scenario: Finalize checklist highlights changed gate fields

**Given**: the run TUI has rendered the finalize checklist
**When**: a gate marker, state, or detail changes on the next TUI refresh
**Then**: the changed gate field or narrowest practical detail fragment is flash-highlighted
**And**: unrelated gates are not flash-highlighted
**And**: the entire checklist panel is not flash-highlighted solely because one gate field changed

#### Scenario: Volatile time counters do not trigger flash highlights

**Given**: the run TUI has rendered quiet duration, last-output age, timeout countdown, elapsed time, or a spinner frame
**When**: the next TUI refresh changes only those time-counter or spinner values
**Then**: no flash highlight is triggered for those natural refresh changes

#### Scenario: Meaningful status-kind changes still trigger flash highlights

**Given**: the run TUI has rendered an agent liveness or timeout display kind
**When**: the next TUI refresh changes the display kind, such as from running to quiet or from timeout not configured to timeout countdown
**Then**: the changed status or timeout kind is flash-highlighted
**And**: subsequent numeric duration or countdown drift does not keep retriggering the flash

#### Scenario: Activity timeline highlights new rows without timestamp-only flash

**Given**: the run TUI has rendered an Activity timeline
**When**: a new run event or agent output row appears on the next TUI refresh
**Then**: the new row or its new semantic detail is flash-highlighted
**And**: timestamp-only changes do not trigger a flash highlight

### Requirement: Run command SHALL execute configured lifecycle hooks

`review-gauntlet run` SHALL allow Review Gauntlet configuration to define local command hooks for supported run lifecycle events. Hook commands SHALL execute when their configured event is emitted, SHALL use argv-style execution with `shell=False`, SHALL run in declaration order for a given event, and SHALL use bounded timeouts. Hook execution SHALL be an integration side effect and SHALL NOT alter review coverage, finding state, finalization state, or checkpoint commit semantics.

#### Scenario: Hook runs for configured run lifecycle event

**Given**: an active review session
**And**: the effective Review Gauntlet config defines a `run_started` hook command that writes a marker file
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the hook command is executed when the `run_started` event is emitted
**And**: the marker file contains evidence from the actual hook subprocess
**And**: the run result remains determined by the normal run workflow

#### Scenario: Multiple hooks for one event run in declaration order

**Given**: the effective Review Gauntlet config defines two hook commands for `agent_finished`
**When**: `review-gauntlet run` emits `agent_finished`
**Then**: both hook commands are executed
**And**: the first configured hook is attempted before the second configured hook
**And**: each hook attempt has separate persisted execution evidence

#### Scenario: High-frequency refresh event is not hookable by default

**Given**: a config file defines a hook for `status_refreshed`
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: validation fails with an actionable unsupported hook event error
**And**: no hook command is executed

### Requirement: Hook configuration SHALL be validated before hook execution

Hook configuration SHALL be validated as part of the same JSON/JSONC config loading and effective-config inspection path used for command adapters. Hook commands SHALL reject shell-string-style commands containing whitespace, invalid environment variable names, unsupported template variables, unsafe cwd resolution, and non-finite or non-positive timeout values before executing any hook subprocess.

#### Scenario: Valid hook config appears in effective config

**Given**: a repository or user environment with a valid Review Gauntlet config containing hooks
**When**: the developer runs `review-gauntlet config effective --format json`
**Then**: stdout displays the merged hook configuration
**And**: the hook commands, args, cwd, env, and timeout values are represented in parseable JSON

#### Scenario: Invalid hook command is rejected before execution

**Given**: a config file whose hook command is `echo hello` as a single shell-string command value
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: validation fails with an actionable hook command validation error
**And**: no adapter or hook command is executed

#### Scenario: Invalid hook template is rejected before execution

**Given**: a config file whose hook args contain an unsupported template variable `{unknown_value}`
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: validation fails with an actionable template validation error
**And**: no adapter or hook command is executed

### Requirement: Hook commands SHALL receive structured event context and preserve diagnostics

When executing a hook command, `review-gauntlet run` SHALL provide scalar template variables for common event context and SHALL provide the full event as JSON in the hook subprocess environment. Each hook attempt SHALL persist stdout, stderr, argv, cwd, return code, timeout or failure details, event type, and artifact metadata under `.review-gauntlet` without recording a full inherited environment dump.

#### Scenario: Hook receives event JSON environment

**Given**: the effective config defines a `step_started` hook command that writes `$REVIEW_GAUNTLET_EVENT_JSON` to a file
**When**: `review-gauntlet run` emits `step_started`
**Then**: the hook subprocess receives `REVIEW_GAUNTLET_EVENT_JSON`
**And**: the JSON contains the emitted event `type`, `timestamp`, and step payload
**And**: the hook subprocess also receives scalar environment values for event type, repo root, and state dir

#### Scenario: Hook templates expand event values

**Given**: the effective config defines an `agent_finished` hook with args containing `{event_type}` and `{returncode}`
**When**: `review-gauntlet run` emits `agent_finished` after an agent subprocess exits with code `0`
**Then**: the hook command receives argv values containing `agent_finished` and `0`
**And**: missing optional event fields expand to empty strings rather than invented values

#### Scenario: Hook artifacts preserve failure diagnostics without masking run result

**Given**: the effective config defines a hook command that exits non-zero for `finalized`
**And**: the active session otherwise finalizes successfully
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the run result reports normal successful completion
**And**: the hook attempt persists stdout, stderr, argv, return code, and failure reason under `.review-gauntlet`
**And**: the hook failure does not create or modify review findings or coverage rows

#### Scenario: Hook timeout is bounded and diagnostic

**Given**: the effective config defines a hook command with a short positive timeout
**And**: the hook subprocess runs longer than that timeout
**When**: the configured event is emitted during `review-gauntlet run`
**Then**: the hook subprocess is terminated after the configured timeout
**And**: timeout diagnostics are persisted as hook artifacts
**And**: the primary run result is not replaced by the hook timeout

### Requirement: Cancel SHALL abandon the active review session without finalizing

`review-gauntlet cancel` SHALL provide an explicit way to abandon an active review session created by `init` without creating review execution evidence or finalization checkpoint artifacts. Cancellation SHALL be a durable session lifecycle transition to `cancelled`, not an implicit claim that review coverage or findings are complete.

#### Scenario: Cancel clears active session marker

**Given**: a repository with an active review session created by `review-gauntlet init`
**When**: the developer runs `review-gauntlet cancel --format json`
**Then**: stdout reports the cancelled `session_id`
**And**: stdout reports `session_state: cancelled`
**And**: `.review-gauntlet/active-session.json` no longer exists
**And**: the session ledger records the session state as `cancelled`

#### Scenario: Cancel does not create review or checkpoint evidence

**Given**: a repository with an active review session that has not been finalized
**When**: the developer runs `review-gauntlet cancel`
**Then**: no review run row is created by cancellation
**And**: no latest checkpoint files are written or updated by cancellation
**And**: review cells and findings are not marked reviewed, verified, waived, or finalized solely because the session was cancelled

#### Scenario: Cancelled session cannot be continued as active

**Given**: a repository whose active review session was cancelled successfully
**When**: the developer runs `review-gauntlet status`, `review-gauntlet ready`, or `review-gauntlet review` without running a new `init`
**Then**: the command fails with actionable no-active-session guidance
**And**: the cancelled session is not silently resumed
**And**: a subsequent `review-gauntlet init` creates a new active session ID

#### Scenario: Cancel requires an active session

**Given**: a repository without `.review-gauntlet/active-session.json`
**When**: the developer runs `review-gauntlet cancel`
**Then**: the command fails with actionable no-active-session guidance
**And**: it does not create a new review session, review run, or checkpoint artifact

#### Scenario: Cancel is documented as distinct from finalize

**Given**: a developer reads the review lifecycle documentation
**When**: they need to abandon an accidental `init`
**Then**: the documentation identifies `review-gauntlet cancel` as the supported command
**And**: the documentation distinguishes cancellation from `finalize` by stating that cancellation does not write a review checkpoint

### Requirement: Review adapter startup failures SHALL be structured

When a command-backed review or verification attempt cannot start its external process because subprocess startup raises `OSError`, `review-gauntlet` SHALL report a structured failed-cell result instead of exposing a raw Python traceback as the final user-facing result. Resource exhaustion errors including `EMFILE` and `ENFILE` SHALL be distinguishable from missing-command startup failures and SHALL include actionable retry guidance.

#### Scenario: Adapter startup resource exhaustion is structured

**Given**: an active session with a selected review cell using the external command adapter
**And**: starting the adapter command raises `OSError` with `errno.EMFILE`
**When**: the developer runs `review-gauntlet review --format json`
**Then**: stdout contains a parseable failed-run JSON result with `failed_cell_id` and `failure` details
**And**: the failure details identify resource exhaustion rather than command-not-found
**And**: the failure details include actionable guidance to reduce concurrency or increase the open-file limit
**And**: the command exits non-zero without printing a raw traceback as the final user-facing result
**And**: the failed cell remains pending or stale for retry

#### Scenario: Concurrent review preserves successful sibling cells after startup exhaustion

**Given**: an active session with multiple selected review cells
**And**: one selected cell's external command startup raises `OSError` with `errno.EMFILE`
**And**: at least one other selected cell succeeds in the same run
**When**: the run finalizes
**Then**: successful selected cells are recorded as reviewed
**And**: findings and occurrences from successful cells are persisted
**And**: the failed cell remains non-reviewed and visible for later retry

### Requirement: Review and verification concurrency SHALL default to three

`review-gauntlet review` and `review-gauntlet verify-fixes` SHALL use a default concurrency of `3` when the developer does not pass `--concurrency`. Explicit positive `--concurrency` values SHALL continue to override the default and SHALL retain existing validation and worker-cap behavior.

#### Scenario: Review without explicit concurrency uses three workers

**Given**: an active session with enough eligible pending review cells for concurrent execution
**When**: the developer runs `review-gauntlet review` without `--concurrency`
**Then**: adapter review work executes for no more than three selected cells at the same time
**And**: review budget, selected-cell eligibility, target policy, and successful-cell-only coverage semantics remain unchanged

#### Scenario: Verify-fixes without explicit concurrency uses three workers

**Given**: an active session with enough fixed-pending findings for concurrent verification work
**When**: the developer runs `review-gauntlet verify-fixes` without `--concurrency`
**Then**: adapter verification work executes for no more than three selected cells at the same time
**And**: verification target selection and fixed-finding state transition semantics remain unchanged

#### Scenario: Explicit concurrency still overrides the default

**Given**: an active session with enough eligible cells for concurrent execution
**When**: the developer runs `review-gauntlet review --concurrency 2`
**Then**: adapter review work executes for no more than two selected cells at the same time
**And**: the default concurrency of `3` is not applied to that invocation

### Requirement: Run TUI overview SHALL show actionable coverage projections instead of the full matrix

`review-gauntlet run` interactive TUI SHALL treat the full file × rule coverage matrix as internal session state and SHALL NOT render the complete matrix in the overview screen. The overview SHALL display actionable projections derived from current review cells and live findings: session status, coverage summary, finalize blockers, prioritized next review queue, rule coverage summary, file hotlist, open findings, and recent activity. The overview SHALL preserve the existing finalization, coverage, finding, and non-TUI output semantics.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI overview to render queue/aggregate/hotlist projections rather than a wide file-by-rule matrix. -->

#### Scenario: Overview prioritizes the next review queue

**Given**: an active review session with pending cells and actionable findings
**When**: `review-gauntlet run` renders the interactive overview screen
**Then**: the overview displays a prioritized next review queue derived from concrete current review cells
**And**: the queue includes file path, rule ID, review state, priority label, and a concise reason for each visible entry
**And**: the overview does not render every file × rule cell as a complete matrix

#### Scenario: Overview shows rule and file aggregates

**Given**: an active review session with multiple files and rules
**When**: `review-gauntlet run` renders the interactive overview screen at a width that can fit aggregate panels
**Then**: the overview displays rule-level coverage summaries with reviewed, pending, and open-finding counts
**And**: the overview displays a file hotlist with coverage, pending, and finding counts
**And**: the aggregate lists are sorted deterministically so the riskiest or least-complete entries are visible first

#### Scenario: Narrow overview remains actionable

**Given**: an active review session in a narrow terminal
**When**: `review-gauntlet run` renders the interactive overview screen
**Then**: the overview prioritizes session status, coverage summary, finalize blockers, next review queue, and activity
**And**: lower-priority aggregate panels are compacted, stacked, or omitted rather than forcing a wide matrix layout
**And**: the controls explain how to navigate to focused detail views for files, rules, cells, findings, and agent state

### Requirement: Run TUI SHALL provide focused drill-down coverage views

`review-gauntlet run` interactive TUI SHALL provide focused views for file, rule, cell, finding, and agent detail navigation. Matrix-like coverage inspection SHALL be available through file-scoped, rule-scoped, or flat cell table views rather than through the overview screen. The existing stop, interrupt, refresh, and help controls SHALL remain available.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require focused coverage drill-down views while keeping the overview compact and actionable. -->

#### Scenario: Files view shows selected file rule states

**Given**: an active review session with review cells for multiple files
**When**: the developer opens the files view and selects a file
**Then**: the TUI shows that file's rule states and associated finding/evidence summary
**And**: it does not require displaying unrelated files' rule states in the same table

#### Scenario: Rules view shows selected rule file states

**Given**: an active review session with review cells for multiple rules
**When**: the developer opens the rules view and selects a rule
**Then**: the TUI shows files relevant to that rule with their review states and finding counts
**And**: it does not require displaying unrelated rules in the same detail table

#### Scenario: Cells view exposes all cells as a filterable flat table

**Given**: an active review session with many file × rule cells
**When**: the developer opens the cells view
**Then**: the TUI shows cells as a flat sortable or filterable table with state, priority, rule, file, and finding columns
**And**: filters can narrow the table to pending cells, blockers, a rule, a file prefix, or open findings

### Requirement: Run TUI review queue priorities SHALL be deterministic and actionable

`review-gauntlet run` interactive TUI SHALL assign deterministic priority labels to review-cell queue entries. The displayed label SHALL be one of P0, P1, P2, or P3, derived from an internal score or equivalent deterministic ordering. Raw scores SHALL NOT be required in the overview display. Actionable findings, pending cells, high-risk rules, changed files, and finding counts SHALL influence ordering so the queue identifies finalization blockers and high-value review work first. Stale cells SHALL NOT be prioritized differently from reviewed cells.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require deterministic actionable priority labels for the run TUI review queue. -->

#### Scenario: Findings sort ahead of normal pending cells

**Given**: an active review session with a normal pending cell and a cell with an actionable finding
**When**: the run TUI builds the next review queue
**Then**: the cell with an actionable finding is labeled P0 and appears before normal pending cells
**And**: entries with equal priority are ordered deterministically by stable cell attributes

#### Scenario: Queue labels hide raw scoring details

**Given**: an active review session with prioritized review queue entries
**When**: the run TUI renders the overview queue
**Then**: the overview displays P0, P1, P2, or P3 labels
**And**: it does not require exposing raw numeric priority scores to the developer

### Requirement: Run turns SHALL persist JSON continuation verdicts

`review-gauntlet run` SHALL support file-scoped actionable finding turns that are allowed to span multiple external-agent subprocess turns without splitting the selected file's actionable findings into one-finding prompts. For each continuation-aware turn, the generated prompt SHALL identify a repository-confined JSON continuation file under `.review-gauntlet/turns/<session-id>/`, require the external agent to write a valid verdict file before ending the turn, and use any valid previous continuation file for the same session/action/file task as compact next-turn context.

Continuation verdict files SHALL be handoff artifacts only. The session ledger SHALL remain authoritative for finding state, review-cell coverage, and finalization readiness.

The CLI SHALL provide an agent-operable command to validate continuation turn verdict files independently from OCR review-cell verdict validation. The command SHALL reuse the continuation verdict schema, return machine-readable success or failure output when requested, and exit non-zero for invalid continuation verdicts. Generated continuation-aware prompts SHALL instruct agents to run this validation command after writing the turn verdict file, repair invalid output, and re-run validation before ending the turn.

#### Scenario: Finding prompt keeps grouped findings and declares continuation file

**Given**: an active review session with multiple actionable findings for `src/example.py`
**When**: `review-gauntlet run` renders a file-scoped actionable finding prompt for that file
**Then**: the prompt includes all actionable findings for `src/example.py` selected by the current ready action
**And**: the prompt does not split those findings into separate one-finding turns solely because continuation is enabled
**And**: the prompt includes a deterministic continuation JSON file path under `.review-gauntlet/turns/<session-id>/`
**And**: the prompt includes the required JSON schema and valid `verdict` values `continue`, `finish`, and `error`
**And**: the prompt includes a command to validate that exact continuation file path
**And**: the prompt instructs the agent to rewrite the verdict and re-run validation if validation fails
**And**: the prompt instructs the agent not to end the turn until validation succeeds

#### Scenario: Turn verdict validation accepts a valid continuation verdict

**Given**: a continuation JSON file under `.review-gauntlet/turns/<session-id>/` with a valid `schema_version`, `verdict`, `summary`, finding ID lists, `resolutions`, `next_turn_instructions`, and `error`
**When**: the developer or agent runs `review-gauntlet validate-turn-verdict <path> --format json`
**Then**: the command exits successfully
**And**: stdout is parseable JSON containing `valid: true`
**And**: the command does not mutate source files, review cells, findings, or the session ledger

#### Scenario: Turn verdict validation rejects invalid resolution state names

**Given**: a continuation JSON file under `.review-gauntlet/turns/<session-id>/`
**And**: the file contains `resolutions: [{"finding_id": "RGF-0001", "state": "fixed"}]`
**When**: the developer or agent runs `review-gauntlet validate-turn-verdict <path> --format json`
**Then**: the command exits non-zero
**And**: stdout is parseable JSON containing `valid: false`
**And**: the error identifies the invalid continuation verdict schema or invalid resolution state
**And**: the runtime does not wait until after the agent exits to surface the same schema problem

#### Scenario: Turn verdict validation can reject impossible finding transitions

**Given**: an active review session with an `open` finding `RGF-0001`
**And**: a continuation JSON file under `.review-gauntlet/turns/<session-id>/` requests a resolution state that cannot be applied from `open`
**When**: the developer or agent runs `review-gauntlet validate-turn-verdict <path> --format json`
**Then**: the command exits non-zero before any ledger mutation
**And**: stdout is parseable JSON containing `valid: false`
**And**: the error identifies the finding ID and invalid transition

#### Scenario: OCR verdict validation remains separate

**Given**: an OCR review-cell verdict file shaped as `{"comments": []}`
**When**: the developer runs `review-gauntlet validate-verdict <path> --format json`
**Then**: the existing OCR verdict validation behavior remains unchanged
**And**: continuation verdict validation is performed only by the turn-verdict validation command

#### Scenario: Previous continuation context is injected into the next matching prompt

**Given**: an active review session has a valid continuation JSON file for the `triage_findings` task on `src/example.py`
**And**: the file contains `verdict: continue`, a summary, completed finding IDs, remaining finding IDs, and next-turn instructions
**When**: `review-gauntlet run` renders the next prompt for the same session/action/file task
**Then**: the prompt includes a compact previous-turn context derived from that JSON file
**And**: the prompt does not include continuation context from a different file, action, or session
**And**: the session ledger remains the source of truth for which findings are still actionable

#### Scenario: Verdict file allows early completion of a lingering agent process

**Given**: `review-gauntlet run` starts an external agent subprocess for a continuation-aware finding turn
**And**: the subprocess writes a valid continuation JSON file with `verdict: continue`
**And**: the subprocess keeps running after writing the verdict file
**When**: the configured verdict grace period expires
**Then**: `review-gauntlet run` terminates the lingering subprocess
**And**: the run step is classified from the continuation verdict rather than waiting for the quiet-timeout deadline
**And**: stdout, stderr, activity, and verdict artifact paths remain available for diagnosis

#### Scenario: Error verdict fails the run step distinctly

**Given**: a continuation-aware finding turn writes a valid continuation JSON file with `verdict: error`
**When**: `review-gauntlet run` processes the completed turn
**Then**: the run result reports a structured failure reason distinct from command failure, quiet timeout, and overall timeout
**And**: the failure includes the continuation file path and error message
**And**: the active session remains available for later retry

#### Scenario: Missing or malformed required verdict is a structured failure

**Given**: a continuation-aware finding turn exits without writing a valid continuation JSON file
**When**: `review-gauntlet run` processes the completed turn
**Then**: the run result reports a structured missing-or-invalid-verdict failure
**And**: the failure is not reported as a quiet timeout unless the quiet-output deadline was actually reached
**And**: stdout and stderr artifacts remain available for diagnosis

#### Scenario: Continue without ledger progress is stopped

**Given**: a continuation-aware finding turn targets findings `RGF-0001` and `RGF-0002`
**And**: the external agent writes a valid continuation JSON file with `verdict: continue`
**And**: none of the targeted finding or review-cell states changed during the turn
**When**: `review-gauntlet run` compares pre-turn and post-turn target state
**Then**: the run result reports a structured `no_progress` failure
**And**: the failure includes the task key and targeted IDs
**And**: the run does not continue indefinitely with the same unchanged actionable work

#### Scenario: Partial verdict file write is not treated as invalid verdict

**Given**: `review-gauntlet run` starts an external agent subprocess for a continuation-aware finding turn
**And**: the subprocess creates the continuation JSON file but has not finished writing valid JSON yet
**When**: `review-gauntlet run` polls the continuation file during agent execution
**Then**: the incomplete file is treated as not-yet-written
**And**: polling continues normally without reporting `invalid_step_verdict`
**And**: the verdict is detected only after the file contains valid JSON with a recognized `verdict` value

#### Scenario: Verdict file overwrite updates detected verdict

**Given**: `review-gauntlet run` starts an external agent subprocess for a continuation-aware finding turn
**And**: the subprocess writes a valid continuation JSON file with `verdict: continue`
**And**: the subprocess later overwrites the same file with `verdict: finish`
**And**: the grace period from the first detection has not yet expired
**When**: `review-gauntlet run` detects the updated verdict
**Then**: the run uses the most recently validated verdict (`finish`) for step classification

#### Scenario: Verdict grace period defaults to adapter configuration

**Given**: a command adapter configuration with `verdict_grace_seconds: 10`
**And**: `review-gauntlet run` starts a continuation-aware finding turn
**And**: the agent writes a valid verdict file and continues running
**When**: 10 seconds elapse after verdict detection
**Then**: the subprocess is terminated
**And**: the run step uses the detected verdict for classification
**And**: the default 30-second grace period is not applied

#### Scenario: Continuation path traversal is rejected

**Given**: a continuation-aware finding turn
**And**: the task key computation would produce a path component containing `../`
**When**: `review-gauntlet run` computes the continuation file path
**Then**: the path is rejected before being included in the prompt
**And**: no file is read or written outside `.review-gauntlet/turns/<session-id>/`

### Requirement: Run TUI SHALL derive task labels from structured action signals

`review-gauntlet run` interactive TUI SHALL determine the current task label and Activity `step_started` detail from the structured `next_required_action` signal and coverage/finding counts, not by scanning the ready prompt body text. The TUI SHALL NOT use keyword matching, substring search, or any natural-language parsing of the ready prompt to classify the task kind. When `next_required_action` is `run_review`, the TUI SHALL display `REVIEW PENDING CELLS` when `coverage.pending > 0` and `REVIEW CELLS` otherwise. Stale review cells do not produce a distinct task label. When `next_required_action` is missing or holds an unknown value, the TUI SHALL display `READY TASK` without misclassifying the task.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI to derive task labels from next_required_action and coverage counts, and will prohibit ready-prompt text parsing for task classification. -->

#### Scenario: Pending review cells display REVIEW PENDING CELLS despite prompt containing confirmed and fix

**Given**: an active review session with pending review cells and no confirmed findings
**And**: `next_required_action` is `run_review`
**And**: the ready prompt body contains the words `confirmed` and `fix` (as part of review workflow instructions)
**When**: `review-gauntlet run` renders the TUI current-task display
**Then**: the task label is `REVIEW PENDING CELLS`
**And**: the task label is not `FIX CONFIRMED FINDING`

#### Scenario: Stale review cells do not produce a distinct task label

**Given**: an active review session with stale review cells, no pending cells, and no actionable findings
**And**: `next_required_action` is `finalize`
**When**: `review-gauntlet run` renders the TUI current-task display
**Then**: the task label is `FINALIZE SESSION`

#### Scenario: Confirmed findings display FIX CONFIRMED FINDING only when action matches

**Given**: an active review session with confirmed findings
**And**: `next_required_action` is `fix_confirmed_findings`
**When**: `review-gauntlet run` renders the TUI current-task display
**Then**: the task label is `FIX CONFIRMED FINDING`

#### Scenario: Unknown action displays READY TASK

**Given**: a `RunSnapshot` whose `next_required_action` is `None` or an unrecognized string
**When**: the TUI renders the current-task display
**Then**: the task label is `READY TASK`
**And**: no keyword matching is performed on the ready prompt body

#### Scenario: Activity step_started detail uses action from event payload

**Given**: a `step_started` event with `next_required_action` in its payload
**When**: the Activity timeline renders the event detail
**Then**: the detail label is derived from `next_required_action`
**And**: the detail is not derived by parsing the `prompt` field of the event payload

### Requirement: Review SHALL support parallel cell execution in Phase 1

`review-gauntlet review` SHALL execute all pending review cells in parallel during Phase 1. Each cell's review adapter invocation SHALL be read-only with respect to the repository. Successful cells SHALL transition to `REVIEWED` state. Failed cells SHALL remain `PENDING` for retry. The `--parallel N` option SHALL control the maximum number of concurrent adapter invocations, defaulting to the number of available CPU cores.

#### Scenario: All pending cells reviewed in parallel

**Given**: an active session with 5 pending review cells
**When**: the developer runs `review-gauntlet review`
**Then**: all 5 cells are reviewed concurrently
**And**: successful cells are marked `REVIEWED`
**And**: findings from all cells are persisted with state `open`
**And**: the command exits 0 when all cells succeed

#### Scenario: Partial failure preserves coverage

**Given**: an active session with 3 pending review cells
**And**: one adapter invocation fails with an unexpected error
**When**: `review-gauntlet review --format json` completes
**Then**: the 2 successful cells are marked `REVIEWED`
**And**: the failed cell remains `PENDING`
**And**: findings from successful cells are persisted
**And**: the command exits non-zero with structured failure details

#### Scenario: Zero pending cells is a no-op

**Given**: an active session where all cells are already `REVIEWED`
**When**: the developer runs `review-gauntlet review`
**Then**: no new run record is created
**And**: no adapter commands are invoked
**And**: the command exits 0

### Requirement: Resolve SHALL handle finding judgment and fix in a single step

`review-gauntlet resolve` SHALL execute Phase 2: grouping all `open` findings by file path and invoking a resolution agent per file group. The resolution agent SHALL determine each finding as `confirmed` or `dismissed` and, for confirmed findings, apply the corresponding code fix. The agent SHALL output a verdict.json with `resolutions` declaring the final state of each finding.

#### Scenario: Resolution agent confirms and fixes findings

**Given**: an active session with 2 open findings for `src/app.py`
**When**: `review-gauntlet resolve` invokes the resolution agent for `src/app.py`
**And**: the agent outputs verdict.json with `verdict: finish` and `resolutions: [{finding_id: "RGF-0001", state: "confirmed"}, {finding_id: "RGF-0002", state: "dismissed", dismiss_reason: "not applicable"}]`
**Then**: `RGF-0001` transitions to `confirmed`
**And**: `RGF-0002` transitions to `dismissed` with `dismiss_reason: "not applicable"`

#### Scenario: Resolution agent requires continuation

**Given**: an open finding for `src/complex.py`
**When**: the resolution agent outputs verdict.json with `verdict: continue` and `next_turn_instructions: "need to also update imports"`
**Then**: the agent is re-invoked with the previous context and new instructions
**And**: the finding remains `open` until a finish verdict is received

#### Scenario: Resolution agent aborts

**Given**: an open finding for `src/broken.py`
**When**: the resolution agent outputs verdict.json with `verdict: abort` and `error: "cannot determine fix approach"`
**Then**: the finding remains `open`
**And**: the command reports the abort with the error message
**And**: other file groups continue processing independently

### Requirement: Resolve SHALL support parallel file-grouped execution in Phase 2

`review-gauntlet resolve` SHALL execute resolution agents for different file paths concurrently. Findings on the same file path SHALL be handled by a single agent invocation to prevent file write conflicts. The `--parallel N` option SHALL control the maximum number of concurrent file-group agents.

#### Scenario: Non-conflicting files resolved in parallel

**Given**: open findings for `src/a.py` and `src/b.py`
**When**: `review-gauntlet resolve --parallel 2` runs
**Then**: resolution agents for `src/a.py` and `src/b.py` execute concurrently
**And**: both files can be modified independently without conflict

#### Scenario: Single-file findings handled sequentially

**Given**: 3 open findings all on `src/app.py`
**When**: `review-gauntlet resolve` runs
**Then**: all 3 findings are handled by a single agent invocation
**And**: the agent receives all 3 finding contexts in one prompt

### Requirement: Session SHALL progress through two sequential phases

A review session SHALL progress through two sequential phases: Phase 1 (review) where all pending cells are reviewed to produce findings, and Phase 2 (resolve) where all open findings are resolved. The session SHALL NOT interleave review and resolution. Finalization SHALL only be possible after both phases complete.

#### Scenario: Phase 1 must complete before Phase 2 begins

**Given**: an active session with pending cells and open findings
**When**: the developer runs `review-gauntlet resolve`
**Then**: the command reports that Phase 1 is incomplete
**And**: no resolution agents are invoked

#### Scenario: Session is finalizable after both phases

**Given**: an active session with all cells `REVIEWED`
**And**: all findings are `confirmed` or `dismissed`
**And**: review-universe files are clean relative to HEAD
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: finalization succeeds
**And**: checkpoint files are written

### Requirement: Run TUI SHALL show a finalized work summary

`review-gauntlet run` interactive TUI SHALL replace operational next-action panels with a completion-oriented work summary when the run reaches finalized status. The finalized summary SHALL preserve and display the final coverage percentage, reviewed/total cell counts, elapsed runtime, run step count, checkpoint commit metadata when available, resolved finding totals, resolved files, associated rule IDs, and finding IDs. The summary SHALL use explicit zero or none wording for categories that have no values, and SHALL NOT infer success for unknown categories.

The finalized summary SHALL be derived from system-recorded session state, final run result metadata, and checkpoint metadata rather than from an LLM self-report. The normal running, idle, blocked, and failed TUI views SHALL continue to show their operational panels.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the finalized run TUI to present preserved final session outcomes and achievements instead of actionable review-operation panels. -->

#### Scenario: Finalized TUI preserves final progress

**Given**: a run TUI snapshot whose agent status is `finalized`
**And**: the final preserved session coverage is 174 terminal cells out of 200 total cells
**When**: the TUI renders the finalized header and summary
**Then**: the visible progress shows the final non-zero coverage derived from 174/200 cells
**And**: the TUI does not render `0%` solely because the active session file no longer exists

#### Scenario: Finalized TUI highlights completed work

**Given**: a finalized run with resolved findings across multiple files and rules
**And**: the run result includes checkpoint commit metadata
**When**: the TUI renders the finalized summary
**Then**: the summary includes elapsed time and run step count
**And**: the summary includes the checkpoint commit short SHA or an explicit commit-unavailable reason
**And**: the summary includes resolved finding count, resolved file paths, associated rule IDs, and finding IDs

#### Scenario: Finalized TUI hides operational panels

**Given**: a run TUI view whose state class is finalized
**When**: the TUI render sections are built
**Then**: queue, rule coverage, file hotlist, findings projection, and activity content are not rendered as active operational panels
**And**: the finalized summary is the primary body content

#### Scenario: Non-finalized TUI keeps operational panels

**Given**: a run TUI view whose state is running, idle, blocked, or failed
**When**: the TUI render sections are built
**Then**: the existing queue, rule coverage, file hotlist, findings, and activity render paths remain available according to the current active view
**And**: no finalized work summary replaces those panels

#### Scenario: Empty finalized summary categories are explicit

**Given**: a finalized run with no resolved findings and no checkpoint commit SHA
**When**: the TUI renders the finalized summary
**Then**: the summary explicitly reports zero resolved findings or equivalent none wording
**And**: the summary explicitly reports that no checkpoint commit is available or why it was skipped
**And**: it does not omit those categories silently
