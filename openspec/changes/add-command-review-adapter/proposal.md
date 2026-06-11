---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/review_adapter.py
---

# Add configurable external CLI review adapter

**Change Type**: implementation

## Problem / Context

`review-gauntlet` currently has durable review sessions, review cells, finding normalization, and a fake fixture adapter, but no real review execution path. The project constitution requires that reviewed coverage be based on defined prompts, rules, model/tool evidence, and code digest rather than an LLM's self-reporting. The canonical review-session spec already establishes OCR-derived prompts and OCR-style comments as the line-level finding contract.

The missing runtime behavior is a safe, configurable way to delegate review execution to external agent CLIs such as `opencode`, `claude`, or `codex` without embedding provider SDKs, API keys, model-specific dependencies, or orchestration loops inside `review-gauntlet`.

## Proposed Solution

Add a command-based review adapter selected by JSON or JSONC configuration. During `review-gauntlet review`, the CLI shall:

- load adapter configuration from an explicit `--config` path or repository-local default JSON/JSONC files,
- generate an OCR-derived prompt for each selected review cell,
- invoke the configured external command without a shell using argv arrays,
- pass prompts via stdin or prompt files according to configuration,
- collect verdict JSON from stdout or a configured output file,
- validate verdicts into the existing OCR comment contract,
- persist per-cell artifacts for prompt, command metadata, stdout, stderr, and verdict output, and
- update coverage and findings only when the adapter result is valid.

The command adapter must not manage provider credentials directly. Authentication, model selection, and provider-specific login remain responsibilities of the configured external CLI.

## Acceptance Criteria

- A repository can configure review execution with `review-gauntlet.json`, `review-gauntlet.jsonc`, `.review-gauntlet/config.json`, `.review-gauntlet/config.jsonc`, or `review --config <path>`.
- JSONC configuration supports line comments, block comments, and trailing commas while preserving JSON string content.
- The command adapter executes external CLIs without `shell=True` and expands only documented template variables into argv/cwd/env/output paths.
- The adapter supports prompt delivery by stdin and by prompt file.
- The adapter supports verdict collection from stdout JSON and file JSON.
- Verdict JSON is validated into OCR-style comments and existing finding normalization remains the single source of finding records.
- Invalid command execution, timeout, invalid JSON, schema validation failure, missing verdict file, or unsafe output paths leave the selected cell unreviewed and return a non-zero review command result with persisted failure artifacts.
- Existing `--fixture` fake-adapter tests and behavior continue to work for local deterministic verification.
- No LLM SDK dependency or provider API key handling is added to the package.

## Explicit Completion Conditions

- `src/review_gauntlet/review_adapter.py` or adjacent adapter modules expose a fake adapter and a command adapter behind a shared review adapter interface.
- `src/review_gauntlet/cli.py` wires `review --config` and selects the command adapter when a valid JSON/JSONC command configuration is present.
- Adapter artifacts are written under `.review-gauntlet/runs/<run-id>/cells/<cell-id>/` or an equivalently deterministic state path.
- Unit tests cover JSONC parsing, config discovery precedence, template expansion, verdict validation, and safe path handling.
- Integration tests run local fake command scripts for stdout-json and file-json success paths and for representative failure paths.
- The full project check command `make check` passes.

## Out of Scope

- Direct in-process OpenAI, Anthropic, or other LLM SDK integration.
- Automatic credential management, login, or provider configuration for `opencode`, `claude`, `codex`, or other tools.
- Automatic source-code fixes, finding triage decisions, retry loops, CI orchestration, or notification workflows.
- Shell-string execution for configured commands.
