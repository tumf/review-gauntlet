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

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows. File freshness refreshes for a successfully evaluated targeted path SHALL update the stored content digest for all cells on that path without changing unselected sibling cell states.

#### Scenario: Unknown review cell update fails

**Given**: a session ledger without cell `RGC-missing`
**When**: internal reconciliation attempts to update `RGC-missing`
**Then**: the store raises an actionable lookup error
**And**: no caller can treat the missing cell as updated coverage

#### Scenario: Targeted file sibling freshness refresh preserves coverage states

**Given**: an active session with multiple review cells for `file1`
**And**: one `file1` cell is selected and successfully evaluated after `file1` changes
**When**: coverage is reconciled after that successful evaluation
**Then**: all `file1` cells store the current `file1` content digest
**And**: unselected `file1` sibling cells are not marked `stale` solely because `file1` changed
**And**: unselected sibling cells keep their prior coverage states

#### Scenario: Incidental changed files become stale

**Given**: an active session with reviewed cells for `file1` and `file2`
**And**: the current successful review or verification step targets `file1`
**When**: both `file1` and `file2` have changed since their recorded coverage
**Then**: `file1` cells are not stale solely because `file1` was intentionally changed and evaluated
**And**: `file2` cells are stale because `file2` changed incidentally outside the targeted evaluation
**And**: stale `file2` coverage remains visible as a finalization blocker

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

Review Gauntlet SHALL NOT create, remove, merge, or otherwise operate Git linked worktrees. `review-gauntlet finalize` closes a complete active review session into deterministic latest-only checkpoint files; the removed `--merge` flag no longer exists. The checkpoint-only git commit in the run workflow continues to guard against unrelated dirty worktree changes (files outside `.review-gauntlet` that are dirty relative to `HEAD`), but the term "dirty worktree" here refers to uncommitted files in the base repository working directory, not a Git linked worktree.

#### Scenario: Finalize does not expose a merge flag

**Given**: an installed `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet finalize --merge`
**Then**: the command exits with a usage error (exit code 64)
**And**: the error message does not suggest `--merge` as a valid option
**And**: no checkpoint files, branch merges, or worktree cleanup are attempted

#### Scenario: Stale git_worktree metadata does not affect run

**Given**: an active session whose metadata contains `git_worktree.enabled: true` and a `worktree_path` from a pre-removal session
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the agent is invoked with `{repo_root}` expanding to the base repository root
**And**: the default agent cwd is the base repository root
**And**: no `worktree_error` is raised
**And**: the run proceeds or blocks normally based on the current session state

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

#### Scenario: Verify fixes refreshes targeted path sibling freshness

**Given**: an active session with multiple review cells for a path that has a finding in `fixed_pending_verification`
**And**: that path changed while fixing the finding
**When**: `review-gauntlet verify-fixes --format json` successfully evaluates the current review cell for that finding path
**Then**: the finding may transition according to the verification verdict
**And**: all review cells on that targeted path store the current content digest
**And**: unselected sibling cells on that same path are not marked `stale` solely because the targeted path changed
**And**: unselected sibling cells on that same path are not promoted to `pending` solely because the targeted path was evaluated
**And**: unrelated pending or stale cells on other paths are not selected merely to refresh freshness

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

`review-gauntlet init` SHALL create an active review session and review cells, but SHALL NOT start review execution or create a review run. Its output SHALL distinguish the active session lifecycle from the absent review-run lifecycle. When initialized review cells exist, the output SHALL point developers to the command that starts review execution. When no review cells are initialized, the output SHALL NOT identify `review-gauntlet review` as the next command.

<!-- Expected canonical result after archive: the canonical review-sessions spec will make explicit that init next-command guidance is conditional on initialized review cells existing, and zero-cell init does not guide developers toward a no-op review command. -->

#### Scenario: Init creates an active session without starting a run

**Given**: a repository with eligible review files
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: the session ledger contains the initialized review cells
**And**: no review run row is created for the session
**And**: stdout includes `session_state: active`, `run_count: 0`, and a lifecycle field showing that no run has started
**And**: stdout identifies `review-gauntlet review` as the next command for starting review execution

#### Scenario: Init with no review cells does not suggest review

**Given**: a repository target whose changed files are all excluded from review cells
**When**: the developer runs `review-gauntlet init --worktree --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: stdout reports `cell_count: 0`, `run_count: 0`, and `run_state: none`
**And**: stdout does not identify `review-gauntlet review` as `next_command`
**And**: no review run row is created for the session

### Requirement: Ready command SHALL emit the next skill-directed prompt

`review-gauntlet ready` SHALL emit the next skill-directed prompt from concrete renderable work items. It SHALL preserve deterministic priority across pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, and finalize readiness. When aggregate session counts and materialized prompt candidates disagree, `ready` SHALL skip empty candidate buckets and continue to the next valid action instead of crashing while building an impossible file-scoped prompt.

<!-- Expected canonical result after archive: the canonical review-sessions spec will include explicit review-cell bucket drift scenarios in addition to existing finding bucket drift coverage, requiring pending/stale prompt selection to be based on materialized review cells. -->

#### Scenario: Ready skips empty actionable finding bucket

**Given**: an active review session whose aggregate finding counts report confirmed findings
**And**: the concrete ready finding rows available for prompt rendering contain no confirmed finding
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty confirmed-finding bucket
**And**: the command returns the next valid ready prompt or `null` when no promptable work remains

#### Scenario: Ready skips empty pending review-cell bucket

**Given**: an active review session whose aggregate coverage counts report pending review cells
**And**: the concrete ready review-cell rows available for prompt rendering contain no pending review cell
**And**: a later-priority concrete actionable finding exists
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty pending review-cell bucket
**And**: the command returns the later-priority concrete finding prompt

#### Scenario: Ready skips empty stale review-cell bucket

**Given**: an active review session whose aggregate coverage counts report stale review cells
**And**: the concrete ready review-cell rows available for prompt rendering contain no stale review cell
**And**: no concrete actionable review cell or finding exists
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the command does not raise a traceback while selecting the target file
**And**: the command skips the empty stale review-cell bucket
**And**: the command returns `null` when finalization remains blocked by non-promptable state

#### Scenario: Ready priority still uses concrete work

**Given**: an active review session with concrete pending review cells and concrete actionable findings
**When**: the developer runs `review-gauntlet ready --format json`
**Then**: the selected prompt corresponds to the first concrete available category in this order: pending review cells, reopened findings, untriaged findings, confirmed findings, fixed-pending verification findings, stale review cells, finalize
**And**: no category is selected unless it has at least one concrete renderable review cell or finding when that category requires file-scoped work

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

#### Scenario: Agent producing output is shown as running

**Given**: a configured command adapter subprocess is running during `review-gauntlet run`
**And**: the subprocess has produced stdout output within the last 5 seconds
**When**: the TUI refreshes the agent lifecycle snapshot
**Then**: the agent status is displayed as running
**And**: `last_output_age_seconds` reflects the time since the most recent output line
**And**: the Activity panel includes the most recent output lines

#### Scenario: Agent with no recent output is shown as quiet

**Given**: a configured command adapter subprocess is running during `review-gauntlet run`
**And**: the subprocess has not produced any stdout or stderr output for at least 5 seconds
**When**: the TUI refreshes the agent lifecycle snapshot
**Then**: the agent status is displayed as quiet
**And**: `last_output_age_seconds` reflects the time since the last output line or the subprocess start time if no output has been produced

#### Scenario: Output tail is available before process completion

**Given**: a configured command adapter subprocess is running during `review-gauntlet run`
**And**: the subprocess has produced multiple lines of stdout output
**When**: the TUI refreshes the agent lifecycle snapshot before the subprocess exits
**Then**: the agent lifecycle `output_tail` contains the most recent output lines
**And**: the entries are available for Activity panel rendering without waiting for process completion

### Requirement: Ready task prompts SHALL be file-scoped workflows

`review-gauntlet ready` SHALL return a concrete file-scoped task prompt when review cells or findings require action. `review-gauntlet run` SHALL pass that same prompt to the external agent. The prompt SHALL identify one target file and instruct the agent to process that file through triage, optional fix, and marking steps instead of issuing broad state-category instructions such as "triage all untriaged findings" or "review all pending cells."

#### Scenario: Pending review work returns file-scoped task

**Given**: an active session has pending or stale review cells for multiple files
**When**: the developer runs `review-gauntlet ready`
**Then**: the prompt identifies exactly one target `file_path`
**And**: the prompt lists the actionable review cells for that file
**And**: the prompt instructs the agent to review, triage any findings, fix if needed, and mark findings for that file
**And**: the prompt does not instruct the agent to process all pending or stale cells across the session.

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
