## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`review-gauntlet run` SHALL continue to orchestrate active sessions without changing task selection, command execution, result payloads, interruption behavior, JSON output behavior, non-TUI behavior, fallback behavior, or session finalization semantics.

Interactive `run` TUI presentation SHALL render a compact dashboard that is faithful to the target user-facing structure: a `Review Gauntlet` header, a `Next to finalize` checklist, side-by-side `Agent` and `Session` summary panels where terminal width allows, an `Activity` timeline, and compact implemented controls. The TUI SHALL derive a human-facing dashboard view model from raw controller and session state before rendering. That view model SHALL include header fields, finalize checklist rows, agent summary fields, session summary fields, and normalized activity rows. TUI widgets SHALL render the view model rather than directly dumping raw prompt text, raw argv payloads, raw event payloads, raw full session IDs, raw finalize action names, or raw blocker lists.

The header SHALL use a concise two-line summary. The first line SHALL include terminal run status, `gate x/6`, and the current checklist title. The second line SHALL include shortened session id, agent or command display name, a concise liveness label, and timeout label when known. Gate numbering SHALL be displayed in the header only and SHALL NOT be repeated on each checklist row.

The primary progress panel SHALL be titled `Next to finalize` and SHALL render exactly these six ordered checklist rows: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint. Each row SHALL use only one of these TUI state labels: `running`, `done`, `next`, `later`, `blocked`, or `failed`. Internal states such as `pending`, `stale`, `untriaged`, `confirmed`, `reopened`, and `fixed_pending_verification` MAY appear in row details but SHALL NOT be used as primary row states. The TUI SHALL NOT render the old `Resolve finalize blockers` checklist row.

The TUI SHALL classify finalize blockers for display. Coverage blockers, including pending review cells and stale review cells, SHALL be represented by the Review coverage row. Finding blockers, including untriaged, reopened, confirmed, and fixed-pending-verification findings, SHALL be represented by the corresponding finding rows. Finalize-only blockers, including dirty worktree blockers, target digest drift, expired waived or accepted-risk findings, no completed review run, and unclassified finalization blockers, SHALL be represented by Final checks. While any earlier checklist row is incomplete, Final checks SHALL render as `later` with human wording such as `checked after review/findings` rather than displaying a generic finalize blocker count. Final checks SHALL render as `blocked` only when prior rows are complete and finalize-only blockers remain.

The TUI SHALL replace standalone `Session metrics`, standalone `Findings`, and standalone `Current operation` panels with compact `Agent` and `Session` summary panels. The Agent panel SHALL show command label, alive/running/quiet/terminal status, output recency, timeout remaining when known, and artifact path when available. The Session panel SHALL show compact coverage percent and reviewed/total counts, open finding count, current checklist title, and agent step. Coverage denominator rules SHALL continue to exclude superseded cells, and this presentation calculation SHALL NOT mutate durable coverage state.

The Activity panel SHALL mix normalized Review Gauntlet events and bounded agent stdout/stderr tail rows in one timeline. Activity row kinds SHALL be human labels such as `event`, `stdout`, and `stderr`. The TUI MAY synthesize display-only activity rows such as `gate started` from the current view model, but it SHALL NOT synthesize quiet-running agent heartbeat rows such as `agent alive no output for 2m00s` in Activity. When an agent is quiet but still running, the TUI SHALL keep liveness visible in the Header and Agent summary instead of adding or removing Activity rows. Agent output displayed in Activity SHALL remain bounded, line-oriented, sanitized, truncated, and redacted, and full output artifacts SHALL remain the audit source of truth.

The TUI SHALL avoid user-facing internal action names such as `run_review` and `resolve_finalize_blockers`. It SHALL map those internal actions to human wording such as `waiting`, `ready to finalize`, `waits for coverage`, `checked after review/findings`, or the relevant checklist title.

<!-- Expected canonical result after archive: the canonical review-sessions spec will define that quiet-running liveness is displayed in Header and Agent summary, while Activity remains stable by omitting synthetic quiet heartbeat rows. -->

#### Scenario: Run TUI activity mixes events and output without quiet heartbeat rows

**Given**: the run controller has emitted Review Gauntlet events
**And**: the active agent has emitted stdout and stderr output lines
**And**: the agent later becomes quiet while still running
**When**: the TUI renders Activity
**Then**: event rows use the `event` kind and human labels such as `run started`, `gate started`, or `agent started`
**And**: agent stdout rows use the `stdout` kind
**And**: agent stderr rows use the `stderr` kind
**And**: Activity does not contain synthetic quiet heartbeat rows such as `agent alive no output for 2m00s`
**And**: the Header or Agent summary shows the quiet liveness state instead
**And**: displayed output remains bounded, sanitized, truncated, and redacted
