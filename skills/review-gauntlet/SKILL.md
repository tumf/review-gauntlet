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
2. `review-gauntlet review` — advance one step.
3. `review-gauntlet status` — inspect coverage state.
4. `review-gauntlet findings` — inspect findings.
5. `review-gauntlet mark <id> <state> --reason "..."` — record a human decision.
6. `review-gauntlet verify-fixes` — verify fixed-pending findings.
7. `review-gauntlet finalize` — confirm both coverage and findings are closed.

Use `--format json` for all session-scoped commands (`init`, `status`, `review`, `verify-fixes`, `finalize`) so the agent can parse structured output. Use `--audience agent` on `review` and `verify-fixes` when the adapter runs without human interaction.

Run one `review` step at a time. Wait for human action between steps.

## Acting on `next_required_action`

Always read `review-gauntlet status` before deciding the next command. Treat `next_required_action` as the primary instruction for what to do next, and inspect `finalize_blockers`, `coverage`, and `finding_state_counts` for the details.

When it says to run review, run exactly one `review-gauntlet review` step. Then stop and inspect `status` again. Do not loop automatically to completion.

When `next_required_action` is `triage_findings`, treat it as a literal status action, not a function name or code symbol. Do not search the codebase for `triage_findings`. Run `review-gauntlet findings` and classify each `untriaged` or `reopened` finding ID explicitly. Confirm real issues, mark false positives with a reason, or mark fixed only after the code change exists. Do not say triage is complete while any finding remains `untriaged` or `reopened`.

When `next_required_action` is `fix_confirmed_findings`, treat it as the implementation step after triage. `confirmed` is not a terminal triage state; it means the finding has already been accepted as real and now needs fixing, waiving, or accepting risk. Prefer fixing confirmed findings, then mark them `fixed` only after the code change exists. Do not call this triage complete until confirmed findings have moved to `fixed_pending_verification`, `waived`, or `accepted_risk`.

When it says to run verify-fixes, run `review-gauntlet verify-fixes` against the fixed-pending findings. If verification reopens a finding, return to triage. If verification passes, inspect status again before finalizing.

When it says to resolve finalize blockers, read every blocker and resolve the concrete cause before retrying. Common blockers include stale review cells, target digest changes after the last review run, expired waivers or accepted risks, and dirty working tree files. For dirty files, commit or revert review-target changes before finalize; non-review dirty files may be allowed only when the user explicitly wants `--allow-non-review-dirty`.

When it says to finalize, run `review-gauntlet finalize` only after confirming the working tree and blocker policy are acceptable. Finalize creates the checkpoint used as the next review base, so do not finalize over ambiguous local state.

## Review target options

- Default: resume from the latest review checkpoint when one exists; otherwise review every eligible repository file.
- `--worktree`: review staged, unstaged, and untracked files.
- `--from <ref> --to <ref>`: review files changed between two refs.
- `--commit <oid>`: review files changed by a single commit.
- `--all`: review every eligible repository file.

## Review configuration

Do not assume `--config` is required. Use repository defaults unless the user or repository explicitly points to a non-default config. Config files may define the external review adapter and optional execution settings such as `cwd`, `env`, and `timeout_seconds`.

Supported template variables include `{repo_root}`, `{state_dir}`, `{run_id}`, `{run_dir}`, `{cell_id}`, `{cell_dir}`, `{prompt}`, `{output_file}`, `{file_path}`, and `{rule_id}`.

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
