## Implementation Tasks

- [ ] Replace prompt-time file-body transport in `src/review_gauntlet/review_adapter.py` with deterministic file metadata containing `file_size_bytes` and `line_count`. (verification: unit - `tests/test_review_prompts.py` constructs a prompt for known content and asserts the exact size and line count appear)
- [ ] Remove the rendered `## File Content` fenced block from generated prompts while preserving repository root, review cell identity, selected rule guidance, and verdict contract. (verification: unit - `tests/test_review_prompts.py` asserts unique file-body text and fenced file content are absent, while rule guidance and verdict contract remain present)
- [ ] Instruct external reviewers in the prompt to read the target file from `repository_root` plus `file_path` when content inspection is needed. (verification: unit - `tests/test_review_prompts.py` asserts the instruction is present without embedding source text)
- [ ] Preserve command adapter `{prompt}` transport and supported template-variable validation without adding `{prompt_file}` or stdin input modes. (verification: unit - `tests/test_config.py` continues to accept `{prompt}` and reject `{prompt_file}`; `tests/test_command_review_adapter.py` confirms configured commands still receive prompt text through argv/env expansion)
- [ ] Preserve path-safety and missing-file failure behavior before command execution. (verification: unit - existing or new `tests/test_command_review_adapter.py` assertions cover unsafe or missing review cell paths failing without invoking the configured command)
- [ ] Run focused verification for prompt and command adapter behavior. (verification: integration - `uv run pytest tests/test_review_prompts.py tests/test_config.py tests/test_command_review_adapter.py` passes)
- [ ] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate omit-file-content-from-review-prompt --strict`
Expected archive gate: `cflx openspec validate omit-file-content-from-review-prompt --archive-gate`
