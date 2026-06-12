---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/review_adapter.py
  - tests/test_review_prompts.py
  - tests/test_command_review_adapter.py
  - openspec/specs/review-sessions/spec.md
  - openspec/CONSTITUTION.md
---

# Omit File Content From Review Prompt

**Change Type**: implementation

## Problem/Context

The command adapter currently embeds the full target file content in the generated review prompt. Large files such as `uv.lock` produce prompts around hundreds of kilobytes, which makes command-adapter execution fragile and obscures the actual review contract. The user explicitly requested that files not be included directly in the prompt; the prompt should include only file path, size, and line information.

This must remain adapter-neutral. The solution must not reintroduce `{prompt_file}`, stdin transport, or any `opencode`-specific workaround. External tools still receive the repository root and file path, so they can read the file themselves when they need source content.

## Proposed Solution

Change the generated review prompt so it describes the review target through metadata instead of embedding the file body:

- Keep repository root, review cell id, file path, slice id, rule id, and content digest in the prompt.
- Add file metadata for `file_size_bytes` and `line_count`.
- Remove the fenced `## File Content` body from the prompt.
- Add clear prompt text telling external reviewers to inspect the repository file at `repository_root` plus `file_path` when they need file contents.
- Preserve the OCR-derived rule guidance and verdict JSON contract.
- Preserve `{prompt}` argv/env expansion and the current command adapter output modes.

The implementation should compute metadata deterministically from the current review cell file before invoking the command adapter. It should continue to fail safely if the cell path is outside the repository or no longer exists.

## Acceptance Criteria

- Generated prompts do not contain the target file's full content or fenced file-content block.
- Generated prompts contain `file_path`, `content_digest`, `file_size_bytes`, and `line_count` for the target file.
- Generated prompts still include repository root, selected rule guidance, and the OCR-style verdict JSON contract.
- The prompt instructs external tools to read the target file from the repository path when source content is needed.
- Command adapter configs using `{prompt}` continue to work without adding `{prompt_file}`, stdin transport, or adapter-specific behavior.
- Missing or unsafe review cell paths still fail before command execution.
- Prompt-focused tests prove large file contents are excluded while metadata remains present.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/review_adapter.py` no longer passes raw file content into `build_review_prompt()` and instead passes file metadata.
- `build_review_prompt()` renders file metadata and does not render a `## File Content` section containing the file body.
- `tests/test_review_prompts.py` asserts the prompt includes path, size, lines, and digest, and excludes unique file-body text.
- `tests/test_command_review_adapter.py` or equivalent adapter tests prove command adapter invocation still receives a prompt through `{prompt}` and can produce a verdict without prompt-file transport.
- Existing path-safety behavior for missing or unsafe review cell files remains covered.
- Focused prompt/adapter tests pass.
- `make check` passes.
- `cflx openspec validate omit-file-content-from-review-prompt --strict` passes.

## Out of Scope

- Reintroducing `{prompt_file}`, stdin prompt transport, or prompt-file input modes.
- Adding `opencode`, `claude`, `codex`, or any other tool-specific adapter behavior.
- Changing verdict JSON schema, finding normalization, or review cell identity.
- Changing review target selection, file inventory, or line-level finding semantics.
- Adding automatic file excerpts, diff snippets, or chunking. If needed later, those should be separate explicit changes.
