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

`findings` SHALL cap emitted findings to 10 records by default after applying terminal visibility, path filters, and mark filters. `findings --limit N` SHALL cap emitted findings to the requested positive integer limit. `findings --all-findings` SHALL disable the result-size cap without changing terminal visibility. `findings --limit N --all-findings` SHALL fail with a usage error.

`findings` SHALL expose count metadata in both structured and text result payloads. `total` SHALL be the number of findings after terminal visibility, path, and mark filters but before result-size limiting. `returned` SHALL be the number of findings actually emitted. Findings SHALL be ordered deterministically by path, start line, end line, and finding ID before any result-size cap is applied.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. `status` SHALL report `coverage` as an effective read-only view of the active session's current target rather than a raw persisted review-cell count. Effective coverage SHALL be derived by comparing current target cells and current file digests against persisted review-cell rows without mutating the ledger. Current target cells missing from persisted rows SHALL count as `pending`. Current target cells whose persisted digest no longer matches the current digest SHALL count as `stale`. Persisted cells that are no longer part of the current target SHALL remain visible as `superseded` coverage when included in the effective coverage summary. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending, `status` SHALL expose review work as the next required action before exposing live finding work. When pending cells are exhausted but current review cells are stale, `status` SHALL expose live finding work before generic stale review work so fix-driven stale coverage can be handled after finding work. When the last reviewed target digest differs from the current target digest, `status` SHALL NOT expose review work solely because of that whole-target digest drift if all current target cells are already present, reviewed, and have matching content digests. In that complete-coverage case, `status` SHALL continue normal finding-state priority, including fixed-finding verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending, `ready` SHALL prompt for pending review before prompting for reopened, untriaged, confirmed, fixed-pending, or stale work. When pending cells are exhausted but current review cells are stale, `ready` SHALL prompt for live finding work before prompting for generic stale review work. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL NOT return a target-digest-drift review prompt solely because whole-target digest drift exists when current target-cell coverage is complete.

#### Scenario: Status reports changed reviewed cells as effective stale coverage

**Given**: an active review session with a current target cell persisted as `reviewed`
**And**: the target file content changes so the current cell digest no longer matches the persisted digest
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `coverage.stale` greater than `0`
**And**: stdout does not count that changed current cell as `coverage.reviewed`
**And**: the command does not mutate persisted review cell state

#### Scenario: Status reports missing current target cells as effective pending coverage

**Given**: an active review session whose current target contains a review cell that is absent from persisted `review_cells`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `coverage.pending` greater than `0`
**And**: `next_required_action` is `run_review`
**And**: the command does not insert the missing review cell into the ledger

#### Scenario: Status preserves whole-target digest drift behavior when cell coverage is current

**Given**: an active review session whose current target cells are all present in the ledger
**And**: all current target cells are `reviewed` with matching content digests
**And**: the last reviewed target digest differs from the current target digest only at the whole-target freshness layer
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON with `coverage.reviewed` for the current target cells
**And**: `next_required_action` is not `run_review` solely because of the whole-target digest drift
**And**: the command does not mutate persisted review cell state

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

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
**And**: no latest checkpoint file is created or overwritten
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed

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
