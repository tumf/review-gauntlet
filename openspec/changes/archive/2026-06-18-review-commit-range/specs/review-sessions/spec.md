# Spec Delta: Review Sessions (commit-range review)

## ADDED Requirements

### Requirement: Review target SHALL be pinned to a commit

Review-gauntlet SHALL review committed code rather than the working tree. When a session is initialized, the current `HEAD` commit SHALL be recorded as `review_head_commit`. Review cell content digests SHALL be computed from `git show <review_head_commit>:<path>` instead of `path.read_bytes()`. Fixes and verification SHALL operate on the working tree without invalidating the review target.

#### Scenario: Init records review head commit

**Given**: a repository with at least one commit
**When**: the developer runs `review-gauntlet init --format json`
**Then**: the session metadata includes `review_head_commit` equal to the current `HEAD` commit SHA
**And**: review cells are created with content digests from `git show <review_head_commit>:<path>`

#### Scenario: Fix changes do not cause review cell staleness

**Given**: an active session with a review cell for `src/app.py` at commit `abc123`
**And**: the cell has been reviewed (state: `reviewed`)
**When**: the run agent modifies `src/app.py` in the working tree as a fix
**Then**: the cell's state remains `reviewed` (not `stale`)
**And**: the cell's content digest (from committed content at `abc123`) is unchanged

#### Scenario: Verify-fixes uses working tree content

**Given**: an active session with a `fixed_pending_verification` finding on `src/app.py`
**And**: the working tree has been modified to fix the finding
**When**: `review-gauntlet verify-fixes` runs
**Then**: the review cells used for verification have content digests from the working tree (not the review commit)
**And**: the finding is verified against the current file content

#### Scenario: Backward compatibility without review_head_commit

**Given**: a session created before `review_head_commit` was introduced
**When**: `review-gauntlet status` computes coverage
**Then**: cell content digests use `file_digests(root)` (working tree) as before
**And**: the session functions identically to the pre-change behavior

#### Scenario: Commit target as init fallback

**Given**: no latest checkpoint exists
**When**: the developer runs `review-gauntlet init` without target flags
**Then**: the init target is the current `HEAD` commit (all eligible files)
**And**: the session records the target as a `COMMIT` kind with `head_mode: fixed`

## MODIFIED Requirements

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL be the diff from that checkpoint's `review_base_commit` to `HEAD`. If no latest checkpoint exists, the default target SHALL be the current `HEAD` commit (reviewing all eligible repository files). The `--worktree` flag is removed; the `WORKTREE` target kind no longer exists. Callers that need to review uncommitted changes SHALL commit them first.

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
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: stdout reports `cell_count: 0`, `run_count: 0`, and `run_state: none`
**And**: stdout does not identify `review-gauntlet review` as `next_command`
**And**: no review run row is created for the session

#### Scenario: Worktree flag is rejected

**Given**: an installed `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the command exits with a usage error (exit code 64)
**And**: the error message does not suggest `--worktree` as a valid option

### Requirement: Review rules and prompts SHALL port the pinned OCR corpus

The default review logic SHALL derive its bundled prompts, path-based rules, and line-level review comment contract from Alibaba `open-code-review` commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`. The ported corpus SHALL include OCR's system rule map and all built-in rule documents, SHALL be usable without network access, and SHALL be included in the ruleset digest for stale-coverage detection. Review execution adapters SHALL use this OCR-derived prompt and verdict contract when asking external tools to review cells.

Generated review prompts SHALL identify the target file by repository root, repository-relative file path, content digest, file size in bytes, line count, and review commit SHA. Generated prompts SHALL NOT embed the target file body directly. External review tools that need source content SHALL read the target file from the repository path at the specified commit (e.g., via `git show <commit>:<path>`), not from the working tree.

The bundled rule corpus SHALL include a local Solidity rule document selected for `.sol` files. Solidity guidance SHALL cover smart-contract-specific review risks across these required categories: specification and assumptions; Solidity version and compiler settings; access control; reentrancy and external calls; ETH and token transfers; input validation and boundary values; numeric calculation, rounding, and casting; state management and invariants; randomness, time, block data, and on-chain secrecy assumptions; oracle, pricing, and external data; gas and denial-of-service resistance; upgradeable/proxy contracts; signatures, permits, and replay protection; ERC/interface compliance; emergency design; events and auditability; testing and verification; deployment and operations; code quality and readability; and high-risk signal review. The guidance SHALL also include the practical review order of checking specification/invariants, permissions/funds, external calls/reentrancy, accounting/math, high-risk mechanisms, boundary/DoS/gas/error cases, and tests/static analysis/deployment settings.

#### Scenario: External command receives OCR-derived review prompt with commit reference

**Given**: a selected review cell with a file path, content digest, byte size, line count, and rule id
**And**: the session is configured to use an external command adapter
**And**: the session metadata includes `review_head_commit`
**When**: `review-gauntlet review` invokes the adapter
**Then**: the generated prompt includes the selected OCR-derived rule guidance
**And**: the prompt identifies the file and review cell being evaluated
**And**: the prompt includes the target file path, content digest, byte size, line count, and review commit SHA
**And**: the prompt does not embed the target file body
**And**: the prompt instructs the external command to read the target file at the specified commit when content is needed
**And**: the prompt instructs the external command to return the OCR-style verdict JSON contract

### Requirement: Review cells SHALL model coverage independently from finding state

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows. File freshness refreshes for a successfully evaluated targeted path SHALL update the stored content digest for all cells on that path without changing unselected sibling cell states. Review cell staleness SHALL be determined by comparing the persisted content digest with the current content digest at the review target commit; working tree changes from in-session fixes SHALL NOT cause review cells to become stale.

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

## REMOVED Requirements

None — the `--worktree` flag removal is covered under the MODIFIED Init requirement.
