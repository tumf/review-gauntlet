## Implementation Tasks

- [x] Reorder README command guidance so setup is followed by the session review workflow (`init`, `review`, `status`, `findings`, optional `mark`, `finalize`) before any planning/diagnostic commands. (verification: manual - inspected `README.md` lines 17-57 and confirmed the first operational command path starts with `uv run review-gauntlet init`, followed by `review`, `status`, `findings`, optional `mark`, and `finalize`)
- [x] Preserve and clarify target-selection examples around `init`, including worktree, ref range, single commit, and explicit full-repository review. (verification: manual - source path `README.md` lines 25-47 document runnable target-selection commands `uv run review-gauntlet init . --worktree`, `uv run review-gauntlet init . --from main --to HEAD`, `uv run review-gauntlet init . --commit <commit-oid>`, and `uv run review-gauntlet init . --all`)
- [x] Move `inventory`, `plan`, and `report` into a later diagnostic/legacy planning subsection with wording that they inspect file discovery, review slicing, and report rendering rather than drive the normal review lifecycle. (verification: manual - inspected `README.md` lines 65-87 and confirmed repository-verifiable invocations for `uv run review-gauntlet inventory . --format text`, `uv run review-gauntlet plan . --format json`, and `uv run review-gauntlet report .` remain documented after the primary workflow with diagnostic wording)
- [x] Verify the documentation-only implementation does not affect CLI behavior or tests. (verification: integration - `agent-exec run -- make check`, job `0e4d5ed26ce2d9a0b61bda42bc8d3208`, exited 0)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate reorder-readme-command-guidance --archive-gate`
