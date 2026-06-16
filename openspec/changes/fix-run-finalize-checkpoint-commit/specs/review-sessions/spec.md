## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

Dirty review-universe blockers SHALL identify that review-universe files are dirty relative to `HEAD` without including individual dirty file paths in `finalize_blockers`.

When `review-gauntlet run` detects that an agent step successfully finalized the active session, the run workflow SHALL attempt a checkpoint-only git commit for the generated latest checkpoint artifacts before reporting final completion. The checkpoint commit SHALL stage only `.review-gauntlet/checkpoints/latest` and the concrete `status.json`, `findings.json`, `events.json`, and `summary.md` files under the generated checkpoint directory referenced by the current latest pointer. The run workflow SHALL NOT stage or commit product/source files, ledger files, run logs, unrelated review artifacts, stale checkpoint generations, or unrelated dirty worktree changes. If agent stdout does not contain a parseable complete generated-files list, the checkpoint commit helper SHALL derive the allowed generated checkpoint files from the current safe latest pointer. If checkpoint artifacts have no diff, the run workflow SHALL report a successful checkpoint-commit no-op. If unrelated dirty worktree state prevents a safe checkpoint-only commit, the run workflow SHALL surface a structured blocker instead of silently claiming full completion. Standalone `review-gauntlet finalize` and `finalize --merge` SHALL keep their existing commit and merge semantics.

#### Scenario: Run finalization commits checkpoint artifacts when agent stdout is not JSON

**Given**: an active review session with complete reviewed coverage and all live findings closed
**And**: the command adapter invoked by `review-gauntlet run` finalizes the session successfully
**And**: the adapter stdout is not parseable JSON
**And**: the latest pointer safely references the generated checkpoint directory
**And**: generated latest checkpoint files differ from `HEAD`
**And**: no unrelated dirty worktree files are present
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the run workflow creates a git commit containing `.review-gauntlet/checkpoints/latest`
**And**: the commit contains the latest checkpoint directory's `status.json`, `findings.json`, `events.json`, and `summary.md`
**And**: the JSON result reports that checkpoint commit was attempted and created
**And**: the JSON result includes the checkpoint commit SHA

#### Scenario: Run checkpoint commit derives missing generated files from latest pointer

**Given**: an active review session that finalizes during `review-gauntlet run`
**And**: the adapter stdout omits some or all generated checkpoint artifact paths
**And**: `.review-gauntlet/checkpoints/latest` is a normal file containing a path-safe checkpoint id
**And**: the referenced checkpoint directory contains `status.json`, `findings.json`, `events.json`, and `summary.md`
**When**: the run workflow reaches checkpoint commit handling
**Then**: the checkpoint commit allowlist includes the pointer file and the four standard files under the referenced checkpoint directory
**And**: the run workflow can commit those files without requiring agent-reported generated paths

#### Scenario: Run checkpoint commit does not trust unsafe latest pointers

**Given**: an active review session that finalizes during `review-gauntlet run`
**And**: the adapter stdout omits generated checkpoint artifact paths
**And**: `.review-gauntlet/checkpoints/latest` is missing, is a symlink, is a directory, references a nested path, references parent traversal, or references a checkpoint id that is not path-safe
**When**: the run workflow reaches checkpoint commit handling
**Then**: the unsafe latest pointer is not used to expand the checkpoint commit allowlist
**And**: dirty generated files that are not explicitly safe remain visible as checkpoint commit blockers

#### Scenario: Run checkpoint commit keeps unrelated checkpoint generations blocked

**Given**: an active review session that finalizes during `review-gauntlet run`
**And**: the latest pointer safely references the current generated checkpoint directory
**And**: another checkpoint directory has dirty files that are not part of the latest generated checkpoint
**When**: the run workflow reaches checkpoint commit handling
**Then**: the run workflow does not stage or commit the unrelated checkpoint directory
**And**: the run result surfaces a structured checkpoint commit blocker for the unrelated checkpoint files

#### Scenario: Standalone finalize behavior remains unchanged

**Given**: an active review session eligible for finalization
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command writes latest checkpoint files according to existing finalize semantics
**And**: the standalone finalize command does not create the run-only checkpoint commit

#### Scenario: Merge finalization is not double-committed

**Given**: an active Git-worktree-backed review session eligible for merge finalization
**When**: the developer runs `review-gauntlet finalize --merge --format json`
**Then**: the existing session-worktree commit and merge behavior remains authoritative
**And**: the normal-run checkpoint commit path does not create an additional duplicate checkpoint commit
