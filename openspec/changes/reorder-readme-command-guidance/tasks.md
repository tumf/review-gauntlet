## Implementation Tasks

- [ ] Reorder README command guidance so setup is followed by the session review workflow (`init`, `review`, `status`, `findings`, optional `mark`, `finalize`) before any planning/diagnostic commands. (verification: manual - inspect `README.md` and confirm the first operational command path starts with `uv run review-gauntlet init` rather than `inventory`)
- [ ] Preserve and clarify target-selection examples around `init`, including worktree, ref range, single commit, and explicit full-repository review. (verification: manual - inspect `README.md` and confirm each existing target-selection example remains present and tied to session initialization)
- [ ] Move `inventory`, `plan`, and `report` into a later diagnostic/legacy planning subsection with wording that they inspect file discovery, review slicing, and report rendering rather than drive the normal review lifecycle. (verification: manual - inspect `README.md` and confirm all three commands remain documented after the primary workflow with diagnostic wording)
- [ ] Verify the documentation-only implementation does not affect CLI behavior or tests. (verification: integration - run `make check`)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate reorder-readme-command-guidance --archive-gate`
