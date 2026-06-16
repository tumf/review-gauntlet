## Implementation Tasks

- [ ] Replace broad `_READY_PROMPTS` fixed strings with file-scoped ready task generation in `src/review_gauntlet/cli.py`.
  verification: unit - add/extend CLI ready prompt tests covering generated target file output.

- [ ] Select the next actionable file deterministically from current review cells and finding state.
  verification: unit - create a session fixture with two files and assert `ready` emits one target file, not a broad all-files task.

- [ ] Generate a file-scoped workflow prompt that explicitly instructs `triage → fix if needed → mark`.
  verification: unit - assert prompt text includes `triage`, `fix if needed`, `mark`, target `file_path`, and relevant finding/cell IDs.

- [ ] Include actionable per-file review cell and finding identifiers in the prompt.
  verification: unit - assert pending/stale and finding-driven scenarios expose stable IDs in ready output.

- [ ] Preserve `run`/`ready` consistency by continuing to route `run` through the same `_ready_prompt()` output.
  verification: integration - extend run controller or CLI tests with a fake command runner that captures the prompt and compare it to `_ready_prompt()` / `ready` output.

- [ ] Preserve finalization and no-ready behavior.
  verification: unit - existing finalize/no-ready tests pass or are extended to cover unchanged behavior.

- [ ] Run project checks after implementation.
  verification: integration - `make check`.

## Future Work

- Consider later adding structured JSON fields for `target_file`, `workflow_stage`, and `actionable_ids` in `ready --format json`; this proposal only requires the prompt text to be file-scoped.

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate make-ready-tasks-file-scoped --archive-gate`
