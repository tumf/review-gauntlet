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

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root.

#### Scenario: Findings mark filter matches hyphenated public state

**Given**: an active session with a `false_positive` finding
**When**: the developer runs `review-gauntlet findings --all --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list includes that false-positive finding

#### Scenario: Findings path filter rejects traversal

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --path ../src`
**Then**: the command fails with a usage error
**And**: no finding state is modified

#### Scenario: Status works with default root

**Given**: an active review session in the current repository
**When**: the developer runs `review-gauntlet status --format json` from the repository root
**Then**: stdout contains parseable JSON session status
**And**: target digest computation does not fail due to relative and absolute path mixing

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

#### Scenario: Malformed decision metadata blocks finalize without crashing

**Given**: a terminal finding event with malformed JSON metadata or an invalid `until` date
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command returns a structured failure result
**And**: the result includes a blocker for invalid or expired terminal-decision metadata
**And**: no traceback is printed

### Requirement: Existing planning commands SHALL remain compatible

Documentation for planning diagnostics SHALL use the current `--format json` output flag and SHALL NOT instruct users to run removed `--json` flags. Markdown report rendering SHALL preserve table structure by escaping or normalizing dynamic table-cell values such as IDs, statuses, checks, and evidence.

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

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

Command adapter configuration validation SHALL reject invalid environment variable names and SHALL define how literal braces are represented in template-bearing strings. Configuration errors SHALL be reported before adapter execution. Configuration paths and adapter `cwd` settings SHALL resolve under the reviewed repository root. Configuration paths or cwd values that resolve outside the repository SHALL be rejected before executing any adapter command.

Command adapter output path templates SHALL be deterministic before prompt construction. `adapter.output.path` SHALL reject `{prompt}` because the prompt itself can contain the output path and would make prompt-time and read-time path resolution diverge. The `{prompt}` template variable SHALL remain supported for adapter `args` and `env`.

#### Scenario: Adapter env keys are validated

**Given**: a command adapter config whose `env` contains an invalid key such as `BAD-NAME` or an empty string
**When**: the review command loads the config
**Then**: the config is rejected with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Output path rejects prompt template

**Given**: a command adapter config whose `adapter.output.path` contains `{prompt}`
**When**: the review command loads the config
**Then**: the config is rejected with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Prompt template remains available for argv and env

**Given**: a command adapter config whose `args` or `env` contains `{prompt}`
**When**: the review command loads the config
**Then**: the config remains valid
**And**: review execution expands `{prompt}` through the existing adapter prompt transport

#### Scenario: Template literal brace behavior is explicit

**Given**: a command adapter config string containing a literal brace sequence
**When**: the config is loaded
**Then**: review-gauntlet either accepts the documented literal escaping form or rejects the string with an actionable unsupported-template error
**And**: supported variables such as `{prompt}` continue to validate successfully

#### Scenario: Explicit config path outside repository is rejected

**Given**: an active review session
**When**: the developer runs `review-gauntlet review --config /tmp/review-gauntlet.jsonc`
**Then**: the command fails with an actionable configuration error
**And**: no external adapter command is executed

#### Scenario: Adapter cwd outside repository is rejected

**Given**: an active review session with a command adapter config whose `cwd` resolves outside the repository
**When**: `review-gauntlet review` evaluates a cell
**Then**: the selected cell fails with a structured adapter failure
**And**: no command is executed from the out-of-repository working directory

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
