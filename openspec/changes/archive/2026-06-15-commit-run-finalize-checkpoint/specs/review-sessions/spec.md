## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

Dirty review-universe blockers SHALL identify that review-universe files are dirty relative to `HEAD` without including individual dirty file paths in `finalize_blockers`.

When `review-gauntlet run` detects that an agent step successfully finalized the active session, the run workflow SHALL attempt a checkpoint-only git commit for the generated latest checkpoint artifacts before reporting final completion. The checkpoint commit SHALL stage only `.review-gauntlet/checkpoints/latest` and concrete generated checkpoint files. The run workflow SHALL NOT stage or commit product/source files, unrelated review artifacts, or unrelated dirty worktree changes. If checkpoint artifacts have no diff, the run workflow SHALL report a successful checkpoint-commit no-op. If unrelated dirty worktree state prevents a safe checkpoint-only commit, the run workflow SHALL surface a structured blocker instead of silently claiming full completion. Standalone `review-gauntlet finalize` and `finalize --merge` SHALL keep their existing commit and merge semantics.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require normal `review-gauntlet run` finalization to commit generated latest checkpoint files with checkpoint-only staging, while leaving standalone finalize and merge-finalize behavior unchanged. -->

#### Scenario: Successful run finalization commits checkpoint artifacts

**Given**: an active review session with complete reviewed coverage and all live findings closed
**And**: the command adapter invoked by `review-gauntlet run` finalizes the session successfully
**And**: generated latest checkpoint files differ from `HEAD`
**And**: no unrelated dirty worktree files are present
**When**: the developer runs `review-gauntlet run --format json`
**Then**: `.review-gauntlet/checkpoints/latest/status.json` is written
**And**: `.review-gauntlet/checkpoints/latest/findings.json` is written
**And**: `.review-gauntlet/checkpoints/latest/events.json` is written
**And**: `.review-gauntlet/checkpoints/latest/summary.md` is written
**And**: the run workflow creates a git commit containing the latest checkpoint artifacts
**And**: the JSON result reports that checkpoint commit was attempted and created
**And**: the JSON result includes the checkpoint commit SHA

#### Scenario: Run checkpoint commit stages only checkpoint paths

**Given**: an active review session that finalizes during `review-gauntlet run`
**And**: a non-checkpoint source file has dirty staged, unstaged, deleted, renamed, or untracked changes after finalization
**When**: the run workflow reaches checkpoint commit handling
**Then**: the run workflow does not stage or commit the non-checkpoint source file
**And**: the run result surfaces a structured checkpoint commit blocker
**And**: the blocker makes the incomplete checkpoint commit state visible

#### Scenario: Run checkpoint commit no-ops when checkpoint diff is empty

**Given**: an active review session that finalizes during `review-gauntlet run`
**And**: the latest checkpoint artifacts match `HEAD` after finalization
**When**: the run workflow reaches checkpoint commit handling
**Then**: no git commit is created
**And**: the run result reports that checkpoint commit was attempted but not created
**And**: the run result includes a no-op reason such as `no_checkpoint_diff`
**And**: the finalized session remains finalized

#### Scenario: Standalone finalize behavior remains unchanged

**Given**: an active review session eligible for finalization
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command writes latest checkpoint files according to existing finalize semantics
**And**: the standalone finalize command does not create the new run-only checkpoint commit

#### Scenario: Merge finalization is not double-committed

**Given**: an active Git-worktree-backed review session eligible for merge finalization
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: the existing session-worktree commit and merge behavior remains authoritative
**And**: the new normal-run checkpoint commit path does not create an additional duplicate checkpoint commit
