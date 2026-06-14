## Implementation Tasks

- [x] Update review-universe dirty blocker formatting so `DirtyReviewUniverseError.__str__()` returns a stable path-free message while retaining internal `paths` evidence for detection. (verification: unit - update `tests/test_cli_finalize_checkpoint.py` to assert the blocker exists and does not contain `dirty.py`)
- [x] Update commit-resolvable blocker classification so `ready` recognizes the path-free review-universe dirty blocker. (verification: integration - existing or updated `tests/test_cli_ready.py` dirty-finalize prompt coverage passes)
- [x] Preserve non-review dirty blocker behavior and checkpoint safety semantics. (verification: integration - `tests/test_cli_finalize_checkpoint.py` continues to assert non-review dirty file names are still reported and dirty review-universe finalize does not write `.review-gauntlet/checkpoints/latest`)
- [x] Run the project verification suite. (verification: integration - `make check` passes)

## Future Work

- Decide separately whether non-review dirty blockers should also hide file names.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate hide-dirty-review-universe-paths --archive-gate`
