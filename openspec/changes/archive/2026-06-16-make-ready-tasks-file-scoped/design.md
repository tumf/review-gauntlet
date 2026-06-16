# Design: file-scoped ready/run task prompts

## Current flow

- `review-gauntlet ready` calls `_ready_prompt(store, root)` and prints the returned prompt.
- `review-gauntlet run` creates a `RunController` with the same `_ready_prompt` callable and passes the returned prompt to the configured external command adapter.
- Current prompt selection is state-category based via `_READY_PROMPTS`, so the agent sees broad tasks such as "Review pending review cells" or "Triage untriaged findings."

## Target flow

`_ready_prompt()` should build a concrete file-scoped task by:

1. Inspecting current review cells and persisted findings for the active session.
2. Choosing the next actionable file deterministically.
3. Summarizing only that file's actionable cells/findings.
4. Emitting an ordered task body:
   - triage
   - fix if needed
   - mark
5. Returning finalize/no-ready prompts only when no file-scoped action remains.

## File selection priority

The implementation should keep the existing session-level priority order unless tests or existing behavior indicate a safer order:

1. reopened findings
2. untriaged findings
3. confirmed findings
4. fixed-pending-verification findings
5. pending review cells
6. stale review cells
7. finalize guidance

Within the selected category, choose the first stable file according to persisted store order or current cell order. The prompt may include other actionable states for that same file so the agent can complete the file's workflow before stopping.

## Prompt shape

The prompt should be concise but concrete:

```text
Next file-scoped task: triage → fix if needed → mark

Target file:
- file_path: src/foo.py

Current state for this file:
- pending review cells:
  - cell_id: ... rule_id: ...
- stale review cells: none
- findings:
  - finding_id: RGF-0001 state: untriaged rule_id: ...

Instructions:
1. Work on the target file for this task.
2. Triage findings for this file.
3. Fix findings if a code change is needed.
4. Mark handled findings with the appropriate review-gauntlet mark command.
5. Stop when this file has no remaining actionable review cells or findings.
```

## Verification strategy

- Unit tests should cover prompt text generation because the behavior is primarily user-facing command output.
- Integration-style CLI tests should verify `ready` and `run` use the same prompt source.
- Existing review adapter prompt tests remain separate; this change does not alter OCR verdict prompt contracts.
