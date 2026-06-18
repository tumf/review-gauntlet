# Spec Delta: Revert Commit-Range Review Target

## REMOVED Requirements

### Requirement: Review target SHALL be pinned to a commit

The commit-pinned review target requirement and all its scenarios are removed. Review cells use working tree content digests (`file_digests(root)`) via `file_digests_for_session`. The `review_head_commit` metadata field, `file_digests_at_commit()`, and `_review_head_commit()` are deleted. Review tools read source files directly from the working tree rather than via `git show <commit>:<path>`.

Removed scenarios:
- Init records review head commit
- Fix changes do not cause review cell staleness
- Verify-fixes uses working tree content
- Backward compatibility without review_head_commit
- Commit target as init fallback

## MODIFIED Requirements

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL be the diff from that checkpoint's `review_base_commit` to `HEAD`. If no latest checkpoint exists, the default target SHALL be the current working tree (all uncommitted changes: staged, unstaged, and untracked eligible files). The `--worktree` flag is accepted as an explicit request for working tree review; callers that need to review committed changes SHALL use `--commit` or `--from/--to`.

#### Scenario: Worktree flag is accepted

**Given**: an installed `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the session target is a WORKTREE kind reviewing uncommitted changes
**And**: the command exits successfully

#### Scenario: Init with no flags and no checkpoint defaults to worktree

**Given**: a repository with no latest checkpoint
**When**: the developer runs `review-gauntlet init` without target flags
**Then**: the session target is WORKTREE kind
**And**: review cells cover uncommitted working tree changes

### Requirement: Review rules and prompts SHALL port the pinned OCR corpus

The default review logic SHALL derive its bundled prompts, path-based rules, and line-level review comment contract from Alibaba `open-code-review` commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807`. The ported corpus SHALL include OCR's system rule map and all built-in rule documents, SHALL be usable without network access, and SHALL be included in the ruleset digest for stale-coverage detection. Review execution adapters SHALL use this OCR-derived prompt and verdict contract when asking external tools to review cells.

Generated review prompts SHALL identify the target file by repository root, repository-relative file path, content digest, file size in bytes, and line count. Generated prompts SHALL NOT embed the target file body directly. External review tools that need source content SHALL read the target file from the repository working tree path.

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

Review cell state mutations SHALL be durable and explicit. Attempts to update a review cell state for an unknown session/cell pair SHALL fail rather than silently succeeding with zero changed rows. File freshness refreshes for a successfully evaluated targeted path SHALL update the stored content digest for all cells on that path without changing unselected sibling cell states. Review cell staleness SHALL NOT prevent finalization or trigger re-review; stale cells are treated as terminal for the purpose of action selection and finalize gating.
