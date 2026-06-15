## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`review-gauntlet run` SHALL continue to orchestrate active sessions without changing task selection, command execution, result payloads, interruption behavior, JSON output behavior, non-TUI behavior, fallback behavior, or session finalization semantics.

Interactive `run` TUI presentation SHALL render a compact dashboard that is faithful to the target user-facing structure: a `Review Gauntlet` header, a `Next to finalize` checklist, side-by-side `Agent` and `Session` summary panels where terminal width allows, an `Activity` timeline, and compact implemented controls. The TUI SHALL derive a human-facing dashboard view model from raw controller and session state before rendering. That view model SHALL include header fields, finalize checklist rows, agent summary fields, session summary fields, and normalized activity rows. TUI widgets SHALL render the view model rather than directly dumping raw prompt text, raw argv payloads, raw event payloads, raw full session IDs, raw finalize action names, or raw blocker lists.

The header SHALL use a concise two-line summary. The first line SHALL include terminal run status, `gate x/6`, and the current checklist title. The second line SHALL include shortened session id, agent or command display name, a concise liveness label, and timeout label when known. Gate numbering SHALL be displayed in the header only and SHALL NOT be repeated on each checklist row.

The primary progress panel SHALL be titled `Next to finalize` and SHALL render exactly these six ordered checklist rows: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint. Each row SHALL use only one of these TUI state labels: `running`, `done`, `next`, `later`, `blocked`, or `failed`. Internal states such as `pending`, `stale`, `untriaged`, `confirmed`, `reopened`, and `fixed_pending_verification` MAY appear in row details but SHALL NOT be used as primary row states. The TUI SHALL NOT render the old `Resolve finalize blockers` checklist row.

The TUI SHALL classify finalize blockers for display. Coverage blockers, including pending review cells and stale review cells, SHALL be represented by the Review coverage row. Finding blockers, including untriaged, reopened, confirmed, and fixed-pending-verification findings, SHALL be represented by the corresponding finding rows. Finalize-only blockers, including dirty worktree blockers, target digest drift, expired waived or accepted-risk findings, no completed review run, and unclassified finalization blockers, SHALL be represented by Final checks. While any earlier checklist row is incomplete, Final checks SHALL render as `later` with human wording such as `checked after review/findings` rather than displaying a generic finalize blocker count. Final checks SHALL render as `blocked` only when prior rows are complete and finalize-only blockers remain.

The TUI SHALL replace standalone `Session metrics`, standalone `Findings`, and standalone `Current operation` panels with compact `Agent` and `Session` summary panels. The Agent panel SHALL show command label, alive/running/quiet/terminal status, output recency, timeout remaining when known, and artifact path when available. The Session panel SHALL show compact coverage percent and reviewed/total counts, open finding count, current checklist title, and agent step. Coverage denominator rules SHALL continue to exclude superseded cells, and this presentation calculation SHALL NOT mutate durable coverage state.

The Activity panel SHALL mix normalized Review Gauntlet events and bounded agent stdout/stderr tail rows in one timeline. Activity row kinds SHALL be human labels such as `event`, `stdout`, and `stderr`. The TUI MAY synthesize display-only activity rows such as `gate started` and `agent alive` from the current view model. When an agent is quiet but still running, the TUI SHALL render a non-flooding heartbeat row such as `event agent alive no output for 2m00s`. Agent output displayed in Activity SHALL remain bounded, line-oriented, sanitized, truncated, and redacted, and full output artifacts SHALL remain the audit source of truth.

The TUI SHALL avoid user-facing internal action names such as `run_review` and `resolve_finalize_blockers`. It SHALL map those internal actions to human wording such as `waiting`, `ready to finalize`, `waits for coverage`, `checked after review/findings`, or the relevant checklist title.

<!-- Expected canonical result after archive: the canonical review-sessions spec will define the run TUI as a Textual dashboard faithful to the Review Gauntlet / Next to finalize / Agent + Session / Activity mock, with human-facing checklist states, blocker classification, compact summaries, mixed agent activity, and unchanged run semantics. -->

#### Scenario: Run TUI renders the mock-aligned dashboard structure

**Given**: an active review session with a configured command adapter
**And**: the `run` TUI is eligible for an interactive text execution
**When**: the TUI renders the session snapshot
**Then**: the dashboard contains panels titled `Review Gauntlet`, `Next to finalize`, `Agent`, `Session`, and `Activity` in that order
**And**: the dashboard does not render standalone `Session metrics`, `Current operation`, or `Finalize path` panel labels
**And**: task selection, command execution, result payloads, interruption behavior, JSON output behavior, non-TUI behavior, and fallback behavior remain unchanged

#### Scenario: Run TUI renders a two-line header without noisy duplicates

**Given**: an active session whose current checklist row is Review coverage
**And**: the command adapter is `opencode`
**And**: the agent is quiet with a known timeout remaining
**When**: the TUI renders the header
**Then**: the first header line includes `RUNNING`, `gate 1/6`, and `Review coverage`
**And**: the second header line includes the shortened session id, `agent opencode`, a quiet liveness label, and timeout label
**And**: the header does not render raw argv, a full session id, or repeated last-output and quiet labels for the same liveness signal

#### Scenario: Run TUI renders Next to finalize as a checklist

**Given**: an active session with 0 reviewed cells and 9 pending cells
**And**: no open findings have been recorded yet
**When**: the TUI renders `Next to finalize`
**Then**: it renders Review coverage as `running` with detail such as `0 / 9 reviewed, 9 pending`
**And**: it renders Triage findings as `next` with detail such as `waits for coverage`
**And**: it renders Fix confirmed findings as `next` with detail such as `no confirmed findings yet`
**And**: it renders Verify fixes as `next` with detail such as `no fixed-pending findings yet`
**And**: it renders Final checks as `later` with detail such as `checked after review/findings`
**And**: it renders Finalize checkpoint as `later` with detail such as `waiting`
**And**: none of the checklist rows include `gate 1/6`, `gate 2/6`, or other per-row gate numbering

#### Scenario: Run TUI classifies blockers before displaying Final checks

**Given**: an active session whose status payload includes finalize blockers for pending or stale review cells
**And**: coverage is still incomplete
**When**: the TUI renders the checklist
**Then**: Review coverage represents the incomplete coverage state
**And**: Final checks is rendered as `later`, not `blocked`
**And**: the checklist does not render `Resolve finalize blockers`
**And**: the checklist does not render a generic detail such as `1 finalize blocker(s)` for coverage or finding blockers

#### Scenario: Run TUI blocks Final checks only for finalize-only blockers

**Given**: coverage, triage, fixing, and verification checklist rows are complete
**And**: a finalize-only blocker such as an uncommitted worktree file remains
**When**: the TUI renders the checklist
**Then**: Final checks is rendered as `blocked`
**And**: Final checks detail identifies the human blocker, such as uncommitted files
**And**: Finalize checkpoint remains `later` until Final checks is done

#### Scenario: Run TUI hides internal action names

**Given**: the session status contains `next_required_action` values such as `run_review` or `resolve_finalize_blockers`
**When**: the TUI renders header, checklist, Agent, Session, and Activity text
**Then**: the rendered dashboard does not contain `run_review`
**And**: the rendered dashboard does not contain `resolve_finalize_blockers`
**And**: equivalent human wording is shown instead

#### Scenario: Run TUI renders compact Agent and Session summaries

**Given**: an active session with a command label, agent lifecycle state, coverage counts, finding counts, and agent step
**When**: the TUI renders the summary panels
**Then**: the Agent panel shows the command label, status/liveness, output recency, and timeout when known
**And**: the Session panel shows compact coverage percent and reviewed/total counts
**And**: the Session panel shows open finding count, current checklist title, and agent step
**And**: the old expanded coverage text is not the primary dashboard panel

#### Scenario: Run TUI activity mixes events, output, and heartbeat rows

**Given**: the run controller has emitted Review Gauntlet events
**And**: the active agent has emitted stdout and stderr output lines
**And**: the agent later becomes quiet while still running
**When**: the TUI renders Activity
**Then**: event rows use the `event` kind and human labels such as `run started`, `gate started`, or `agent started`
**And**: agent stdout rows use the `stdout` kind
**And**: agent stderr rows use the `stderr` kind
**And**: a quiet running agent produces a non-flooding `event` heartbeat row such as `agent alive` with detail such as `no output for 2m00s`
**And**: displayed output remains bounded, sanitized, truncated, and redacted
