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
- `fixed_pending_verification` is not terminal until a later `resolve` run validates it.
- Finalization requires both coverage closure and live finding closure. Neither is optional.
- Changes to code, rule, prompt, or target digest may invalidate old review evidence.
- Generated prompts never embed the full target file body. They identify the file by path, digest, byte size, and line count. External tools read the file from the repository.
- External review adapters receive argv arrays. Never construct shell strings.
- Adapter config paths and `cwd` must stay under the reviewed repository root.

## Command reference

| Command | Purpose |
|---------|---------|
| `init` | Create a review session with a review target |
| `review` | Advance one review step |
| `status` | Inspect coverage, findings, and next action |
| `findings` | List findings (bounded by default) |
| `mark` | Record a human decision on a finding |
| `resolve` | Resolve open findings with the adapter (replaces verify-fixes) |
| `finalize` | Confirm both coverage and findings are closed |
| `ready` | Show the next ready prompt for the active session |
| `run` | Autonomous review loop with optional TUI |
| `cancel` | Cancel the active session |
| `config` | Manage adapter config (`init`, `preset list/show`, `validate`, `effective`) |
| `validate-verdict` | Validate a verdict JSON payload |
| `validate-turn-verdict` | Validate a turn verdict JSON payload |
| `inventory` | File discovery diagnostics (not for review) |
| `plan` | Legacy review plan (diagnostic only) |
| `report` | Legacy matrix report (diagnostic only) |
| `completion` | Generate shell completion scripts |

## Normal review workflow

Use this sequence when the user asks you to perform a review:

1. `review-gauntlet init` — choose the review target and create the session.
2. `review-gauntlet review` — advance one step.
3. `review-gauntlet status` — inspect coverage state.
4. `review-gauntlet findings --format json` — inspect the bounded default findings page.
5. `review-gauntlet mark <id> <state> --reason "..."` — record a human decision.
6. `review-gauntlet resolve` — resolve open findings with the adapter.
7. `review-gauntlet finalize` — confirm both coverage and findings are closed.

Use `--format json` for all session-scoped commands (`init`, `status`, `review`, `findings`, `resolve`, `finalize`) so the agent can parse structured output. Use `--audience agent` on `review` when the adapter runs without human interaction.

`findings` is intentionally bounded to 10 returned findings by default and reports both `total` and `returned`. Treat `returned < total` as explicit incompleteness: narrow with `--path`, `--mark`, or `--limit N` when working on a subset. For example, use `review-gauntlet findings --mark confirmed --limit 3 --format json` to work a bounded batch, then re-check `total` and `returned` before deciding whether more findings remain. Use `--all-findings` only when the workflow explicitly needs the entire filtered result set in one response, such as a final reconciliation step where the full matching list is required. Do not confuse `--all` with `--all-findings`: `--all` includes terminal findings in visibility, while `--all-findings` disables result-size limiting.

Run one `review` step at a time. Wait for human action between steps.

## Autonomous review with `run`

`review-gauntlet run` drives the full review loop automatically. It repeatedly calls `ready` to get the next prompt, executes the adapter, and loops until no more work is actionable or `--max-steps` is reached.

- `--max-steps N` — maximum ready-prompt executions (default: 100).
- `--config CONFIG` — explicit adapter config path.
- `--no-tui` — disable the interactive Textual TUI; use text output instead.
- `--format json` — structured output.

The `run` controller detects no-progress steps (verdict reports success but no targeted state changed) and schedules retries with diagnostics.

## Acting on `next_required_action`

Always read `review-gauntlet status` before deciding the next command. Treat `next_required_action` as the primary instruction for what to do next, and inspect `finalize_blockers`, `coverage`, and `finding_state_counts` for the details.

### `run_review`

Run exactly one `review-gauntlet review` step. Then stop and inspect `status` again. Do not loop automatically to completion.

### `resolve_findings`

Open findings exist that need attention. Run `review-gauntlet findings` and classify each `untriaged` or `open` finding ID explicitly. Confirm real issues, mark false positives with a reason, or mark fixed only after the code change exists. Then run `review-gauntlet resolve` to verify fixed-pending findings with the adapter. Do not treat `resolve_findings` as a code symbol to search for; it is a status action.

### `resolve_finalize_blockers`

Read every blocker from `finalize_blockers` and resolve the concrete cause before retrying. Common blockers include stale review cells, target digest changes after the last review run, expired waivers or accepted risks, and dirty working tree files. For dirty files, commit or revert review-target changes before finalize; non-review dirty files may be allowed only when the user explicitly wants `--allow-non-review-dirty`.

### `finalize`

Run `review-gauntlet finalize` only after confirming the working tree and blocker policy are acceptable. Finalize creates the checkpoint used as the next review base, so do not finalize over ambiguous local state.

## Review target options

- Default: resume from the latest review checkpoint when one exists; otherwise review every eligible repository file.
- `--worktree`: review staged, unstaged, and untracked files.
- `--from <ref> --to <ref>`: review files changed between two refs.
- `--commit <oid>`: review files changed by a single commit.
- `--all`: review every eligible repository file.

## Review configuration

Do not assume `--config` is required. Use repository defaults unless the user or repository explicitly points to a non-default config. Config files may define the external review adapter and optional execution settings such as `cwd`, `env`, `timeout_seconds`, `quiet_timeout_seconds`, and `verdict_grace_seconds`.

Use `review-gauntlet config` subcommands to manage configuration:

- `config init` — create a config file (use `--preset` for quick setup, e.g. `--preset opencode`; `--global` for user-level default).
- `config preset list` — list available presets.
- `config preset show <name>` — show a preset's content.
- `config validate` — validate an existing config file.
- `config effective` — show the effective merged config for a repository.

Supported template variables include `{repo_root}`, `{state_dir}`, `{run_id}`, `{run_dir}`, `{cell_id}`, `{cell_dir}`, `{prompt}`, `{output_file}`, `{file_path}`, and `{rule_id}`.

Hooks can be configured for lifecycle events via the `hooks` config key with `command`, `args`, `timeout_seconds`, `cwd`, and `env`.

## Output mode

Adapters support two output modes configured via `adapter.output.mode`:

- `stdout-json` (default when no config) — adapter prints verdict JSON to stdout.
- `file-json` — adapter writes verdict to a file specified by `adapter.output.path`.

## Expected verdict format

External adapters must return OCR-style verdict JSON:

```json
{"comments":[{"path":"src/app.py","content":"Issue","start_line":1,"end_line":1}]}
```

Each comment maps to a finding. Comments with `start_line` and `end_line` both `0` are preserved as imprecisely positioned findings rather than discarded.

Use `review-gauntlet validate-verdict` or `review-gauntlet validate-turn-verdict` to validate verdict payloads offline.

## Finding states

Findings transition through these states:

- `untriaged` — newly discovered, needs classification.
- `open` — acknowledged but not yet acted on.
- `confirmed` — accepted as real, needs fixing or risk acceptance.
- `fixed_pending_verification` — fix applied, awaiting `resolve` verification.
- `fixed_verified` — fix confirmed by the adapter (terminal).
- `false_positive` — classified as not a real issue (terminal).
- `accepted_risk` — risk acknowledged, no fix planned (terminal, may have `--until` expiry).
- `waived` — waived with justification (terminal, may have `--until` expiry).
- `dismissed` — dismissed (terminal).

`mark` accepts: `confirmed`, `fixed_pending_verification`, `fixed_verified`, `false_positive`, `accepted_risk`, `waived`, `dismissed`. Optional flags: `--reason`, `--owner`, `--until YYYY-MM-DD`.

## File exclusion behavior

Review sessions exclude paths and suffixes by default: top-level `openspec/`, `tests/`, and `docs/` directories (matched only when they are the first path component, so `src/tests/` is NOT excluded), common test files, and package manifests/lock files. These are omitted from review cells but remain in the broader inventory. This separation is intentional — inventory shows everything, review cells focus on source-level targets.

## Commands you should not use in normal review

- `inventory` — file discovery diagnostics only. Useful for debugging, not for review.
- `plan` — legacy review plan. Diagnostic only.
- `report` — legacy matrix report. Diagnostic only.
- `completion` — generates shell completion scripts. Irrelevant to review execution.
