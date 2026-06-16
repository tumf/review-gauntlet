## Implementation Tasks

- [x] Replace broad `_READY_PROMPTS` fixed strings with file-scoped ready task generation in `src/review_gauntlet/cli.py`.
  verification: unit - tests/test_cli_ready.py::test_ready_prompts_are_skill_directed_and_avoid_coordination_metadata, tests/test_cli_session_review.py::test_ready_emits_one_file_scoped_pending_task_with_workflow_and_cell_ids.

- [x] Select the next actionable file deterministically from current review cells and finding state.
  verification: unit - tests/test_cli_ready.py::test_ready_priority_order_is_deterministic and tests/test_cli_session_review.py::test_ready_emits_one_file_scoped_pending_task_with_workflow_and_cell_ids.

- [x] Generate a file-scoped workflow prompt that explicitly instructs `triage → fix if needed → mark`.
  verification: unit - tests/test_cli_session_review.py::test_ready_emits_one_file_scoped_pending_task_with_workflow_and_cell_ids and tests/test_cli_session_review.py::test_ready_prompt_includes_stable_review_cell_and_finding_ids_for_target_file.

- [x] Include actionable per-file review cell and finding identifiers in the prompt.
  verification: unit - tests/test_cli_session_review.py::test_ready_prompt_includes_stable_review_cell_and_finding_ids_for_target_file asserts stable review cell and finding IDs in ready output.

- [x] Preserve `run`/`ready` consistency by continuing to route `run` through the same `_ready_prompt()` output.
  verification: integration - tests/test_run_controller.py::test_run_controller_completes_when_command_finalizes_session exercises run path; ready/run share the same prompt generator in cli.py.

- [x] Preserve finalization and no-ready behavior.
  verification: unit - tests/test_cli_ready.py::test_ready_outputs_no_ready_task_when_only_blockers_remain and tests/test_cli_ready.py::test_ready_finalize_prompt_mentions_commit_and_does_not_write_checkpoint.

- [x] Run project checks after implementation.
  verification: integration - `make check`.

## Future Work

- Consider later adding structured JSON fields for `target_file`, `workflow_stage`, and `actionable_ids` in `ready --format json`; this proposal only requires the prompt text to be file-scoped.

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate make-ready-tasks-file-scoped --archive-gate`
