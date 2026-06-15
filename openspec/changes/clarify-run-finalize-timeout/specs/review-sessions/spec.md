## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`review-gauntlet run` SHALL continue to orchestrate active sessions without changing task selection, command execution, result payloads, interruption behavior, JSON output behavior, non-TUI behavior, fallback behavior, or session finalization semantics.

Interactive `run` TUI presentation SHALL render a compact dashboard that is faithful to the target user-facing structure: a `Review Gauntlet` header, a `Next to finalize` checklist, side-by-side `Agent` and `Session` summary panels where terminal width allows, an `Activity` timeline, and compact implemented controls. The TUI SHALL derive a human-facing dashboard view model from raw controller and session state before rendering. That view model SHALL include header fields, finalize checklist rows, agent summary fields, session summary fields, and normalized activity rows. TUI widgets SHALL render the view model rather than directly dumping raw prompt text, raw argv payloads, raw event payloads, raw full session IDs, raw finalize action names, or raw blocker lists.

The header SHALL use a concise two-line summary. The first line SHALL include terminal run status, `gate x/6`, and the current checklist title. The second header line SHALL follow the canonical header timeout policy. Gate numbering SHALL be displayed in the header only and SHALL NOT be repeated on each checklist row.

The primary progress panel SHALL be titled `Next to finalize` and SHALL render exactly these six ordered checklist rows: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint. Each row SHALL use only one of these TUI state labels: `running`, `done`, `next`, `later`, `blocked`, or `failed`. Internal states such as `pending`, `stale`, `untriaged`, `confirmed`, `reopened`, and `fixed_pending_verification` MAY appear in row details but SHALL NOT be used as primary row states. The TUI SHALL NOT render the old `Resolve finalize blockers` checklist row.

The TUI SHALL classify finalize blockers for display. Coverage blockers, including pending review cells and stale review cells, SHALL be represented by the Review coverage row. Finding blockers, including untriaged, reopened, confirmed, and fixed-pending-verification findings, SHALL be represented by the corresponding finding rows. Finalize-only blockers, including dirty worktree blockers, target digest drift, expired waived or accepted-risk findings, no completed review run, and unclassified finalization blockers, SHALL be represented by Final checks. While any earlier checklist row is incomplete, Final checks SHALL render as `later` with human wording such as `checked after review/findings` rather than displaying a generic finalize blocker count. Final checks SHALL render as `blocked` only when prior rows are complete and finalize-only blockers remain.

When the external command adapter times out, the TUI SHALL preserve the agent lifecycle status as timed out for auditability. If the latest session status is still eligible to finalize with `can_finalize=true` and no finalize blockers, the checklist SHALL treat Review coverage, Triage findings, Fix confirmed findings, Verify fixes, and Final checks as complete and SHALL render Finalize checkpoint as a recoverable manual-finalize state, not as a generic failed review gate. The recoverable state SHALL show concise wording that tells the user the session is ready and can be finalized with `review-gauntlet finalize` or equivalent command wording. If the timeout occurs before finalization eligibility, or if finalize blockers remain, the TUI SHALL NOT show the manual-finalize-ready cue and SHALL continue to show the first incomplete or blocked checklist row.

The TUI SHALL replace standalone `Session metrics`, standalone `Findings`, and standalone `Current operation` panels with compact `Agent` and `Session` summary panels. The Agent panel SHALL show command label, alive/running/quiet/terminal status, output recency, effective timeout remaining or timeout configuration when known, and artifact path when available. Configured command adapters, including adapters using the default timeout, SHALL NOT render timeout as unset. Timeout wording SHALL be concise and SHALL NOT duplicate labels such as `timeout timeout not set`. The Session panel SHALL show compact coverage percent and reviewed/total counts, open finding count, current checklist title, and agent step. Coverage denominator rules SHALL continue to exclude superseded cells, and this presentation calculation SHALL NOT mutate durable coverage state.

The Activity panel SHALL mix normalized Review Gauntlet events and bounded agent stdout/stderr tail rows in one timeline. Activity row kinds SHALL be human labels such as `event`, `stdout`, and `stderr`. The TUI MAY synthesize display-only activity rows such as `gate started` from the current view model, but it SHALL NOT synthesize quiet-running agent heartbeat rows such as `agent alive no output for 2m00s` in Activity. When an agent is quiet but still running, the TUI SHALL keep liveness visible in the Header and Agent summary instead of adding or removing Activity rows. Agent output displayed in Activity SHALL remain bounded, line-oriented, sanitized, truncated, and redacted, and full output artifacts SHALL remain the audit source of truth.

The TUI SHALL avoid user-facing internal action names such as `run_review` and `resolve_finalize_blockers`. It SHALL map those internal actions to human wording such as `waiting`, `ready to finalize`, `waits for coverage`, `checked after review/findings`, or the relevant checklist title.

<!-- Expected canonical result after archive: the canonical review-sessions spec will distinguish adapter timeout from finalize readiness, show manual finalize recovery when a timed-out agent leaves a session ready to finalize, and keep effective adapter timeout display accurate without changing command execution or finalization semantics. -->

#### Scenario: Run TUI shows manual finalize recovery after ready adapter timeout

**Given**: an active session whose latest status has `can_finalize=true`
**And**: the status has no finalize blockers
**And**: coverage, triage, fixing, verification, and final checks are complete
**And**: the external command adapter timed out before invoking finalization
**When**: the TUI renders the finalize checklist and Agent summary
**Then**: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, and Final checks are not marked failed
**And**: Finalize checkpoint indicates that the agent timed out but the session is ready for manual finalization
**And**: the rendered text includes `review-gauntlet finalize` or equivalent concise recovery wording
**And**: the Agent summary still exposes the timed-out lifecycle state for auditability

#### Scenario: Run TUI preserves failure before finalize readiness

**Given**: an active session whose latest status has `can_finalize=false`
**And**: coverage or finding work remains incomplete
**And**: the external command adapter timed out
**When**: the TUI renders the finalize checklist
**Then**: the first incomplete checklist row is shown as incomplete or failed according to the existing failure rules
**And**: Finalize checkpoint does not show the manual-finalize-ready recovery cue

#### Scenario: Run TUI preserves blockers after adapter timeout

**Given**: an active session whose latest status has finalize blockers
**And**: the external command adapter timed out
**When**: the TUI renders the finalize checklist
**Then**: Final checks or the relevant earlier checklist row shows the blocker state
**And**: Finalize checkpoint does not show the manual-finalize-ready recovery cue

#### Scenario: Agent summary uses effective adapter timeout wording

**Given**: an active session with a configured command adapter that uses the default timeout
**When**: the TUI renders the Agent summary before or after a command adapter timeout
**Then**: the Agent summary does not render timeout as unset
**And**: the Agent summary does not duplicate timeout labels such as `timeout timeout not set`
**And**: timeout enforcement, command execution, JSON output, non-TUI behavior, and session finalization semantics remain unchanged
