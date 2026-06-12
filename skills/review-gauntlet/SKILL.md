---
name: review-gauntlet
description: Guidance for agents that use review-gauntlet as a tool to perform coverage-tracked code reviews. Use when asked to run, continue, inspect, verify, or finalize a review-gauntlet review session; triage findings; check unreviewed/stale coverage; or operate review-gauntlet through an external review tool adapter.
---

# review-gauntlet operations guide

## What it does

`review-gauntlet` drives a coverage-tracked code review process. You initialize a session with a review surface, advance review step by step, track findings, and finalize only when coverage and all findings are closed.

The goal is not to claim code is bug-free. The goal is to guarantee that a defined review surface was inspected with durable evidence before the project is called reviewed.

## Core constraints you must follow

When the user asks you to use review-gauntlet, obey these constraints:

- `review` advances exactly one step. Do not loop it until coverage is complete.
- `reviewed` means "executed against the defined target/rule/slice/prompt/model/digest," not "code is safe."
- Unreviewed, failed, stale, and needs-retry states must remain visible. Do not hide incompleteness.
- Findings have stable IDs. A re-detected issue must reuse the same finding identity.
- Human decisions (waived, accepted-risk, fixed, etc.) are ledger entries. Record reason, actor, and timestamp.
- `fixed` is not terminal until a later `verify-fixes` run validates it.
- Finalization requires both coverage closure and live finding closure. Neither is optional.
- Changes to code, rule, prompt, or target digest may invalidate old review evidence.
- Generated prompts never embed the full target file body. They identify the file by path, digest, byte size, and line count. External tools read the file from the repository.
- External review adapters receive argv arrays. Never construct shell strings.
- Adapter config paths and `cwd` must stay under the reviewed repository root.

## Normal review workflow

Use this sequence when the user asks you to perform a review:

1. `review-gauntlet init` — choose the review target and create the session.
2. `review-gauntlet review --config <config-file>` — advance one step.
3. `review-gauntlet status` — inspect coverage state.
4. `review-gauntlet findings` — inspect findings.
5. `review-gauntlet mark <id> <state> --reason "..."` — record a human decision.
6. `review-gauntlet verify-fixes --config <config-file>` — verify fixed-pending findings.
7. `review-gauntlet finalize` — confirm both coverage and findings are closed.

Run one `review` step at a time. Wait for human action between steps.

## Review target options

- Default (workspace diff): review staged, unstaged, and untracked files.
- `--from <ref> --to <ref>`: review files changed between two refs.
- `--commit <oid>`: review files changed by a single commit.
- `--all`: review every eligible repository file.

## Review configuration

Configuration lives in `.review-gauntlet/config.jsonc`, `review-gauntlet.jsonc`, or is passed via `--config`. A minimal config:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "--dangerously-skip-permissions", "{prompt}"],
    "output": {"mode": "file-json", "path": "{output_file}"}
  }
}
```

Supported template variables in config include `{repo_root}`, `{state_dir}`, `{run_id}`, `{run_dir}`, `{cell_id}`, `{cell_dir}`, `{prompt}`, `{output_file}`, `{file_path}`, and `{rule_id}`.

Optional config keys: `cwd` (defaults to caller's cwd), `env` (defaults to inherited environment), `timeout_seconds` (defaults to 600).

## Expected verdict format

External adapters must return OCR-style verdict JSON:

```json
{"comments":[{"path":"src/app.py","content":"Issue","start_line":1,"end_line":1}]}
```

Each comment maps to a finding. Comments with `start_line` and `end_line` both `0` are preserved as imprecisely positioned findings rather than discarded.

## File exclusion behavior

Review sessions exclude paths and suffixes by default: `openspec/`, `tests/`, `docs/`, common test files, and package manifests/lock files. These are omitted from review cells but remain in the broader inventory. This separation is intentional — inventory shows everything, review cells focus on source-level targets.

## Commands you should not use in normal review

- `inventory` — file discovery diagnostics only. Useful for debugging, not for review.
- `plan` — legacy review plan. Diagnostic only.
- `report` — legacy matrix report. Diagnostic only.
- `completion` — generates shell completion scripts. Irrelevant to review execution.
