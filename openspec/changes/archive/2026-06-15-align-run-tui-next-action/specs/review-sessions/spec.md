## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

Interactive `run` TUI presentation SHALL render a compact dashboard that is faithful to the target user-facing structure: a `Review Gauntlet` header, a `Finalize checklist` progress checklist, side-by-side `Agent` and `Session` summary panels where terminal width allows, an `Activity` timeline, and compact implemented controls. The TUI SHALL derive a human-facing dashboard view model from raw controller and session state before rendering. That view model SHALL include header fields, finalize checklist rows, agent summary fields, session summary fields, and normalized activity rows. TUI widgets SHALL render the view model rather than directly dumping raw prompt text, raw argv payloads, raw event payloads, raw full session IDs, raw finalize action names, or raw blocker lists.

The primary progress panel SHALL be titled `Finalize checklist` and SHALL render exactly these six ordered checklist rows: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint. Each row SHALL use only one of these TUI state labels: `running`, `done`, `next`, `later`, `blocked`, or `failed`. Internal states such as `pending`, `stale`, `untriaged`, `confirmed`, `reopened`, and `fixed_pending_verification` MAY appear in row details but SHALL NOT be used as primary row states. The TUI SHALL NOT render the old `Resolve finalize blockers` checklist row.

The TUI SHALL use known `next_required_action` values from session status as the authoritative source for selecting the current `Finalize checklist` row in the header, Session summary, and checklist presentation. The mapping SHALL be: `run_review` to Review coverage, `triage_findings` to Triage findings, `fix_confirmed_findings` to Fix confirmed findings, `run_verify_fixes` to Verify fixes, `resolve_finalize_blockers` to Final checks, `finalize` to Finalize checkpoint, and `cleanup_git_worktree` to Finalize checkpoint. The TUI SHALL keep actual coverage, finding, and blocker details visible even when `next_required_action` selects a later checklist row. If `next_required_action` is missing or unknown, the TUI SHALL fall back to deriving the current checklist row from coverage, finding counts, blockers, finalization state, and failure state.

The TUI SHALL classify finalize blockers for display. Coverage blockers, including pending review cells and stale review cells, SHALL be represented by the Review coverage row. Finding blockers, including untriaged, reopened, confirmed, and fixed-pending-verification findings, SHALL be represented by the corresponding finding rows. Finalize-only blockers, including dirty worktree blockers, target digest drift, expired waived or accepted-risk findings, no completed review run, and unclassified finalization blockers, SHALL be represented by Final checks. While any earlier checklist row is incomplete and no known `next_required_action` selects Final checks, Final checks SHALL render as `later` with human wording such as `checked after review/findings` rather than displaying a generic finalize blocker count. Final checks SHALL render as `blocked` when `next_required_action` is `resolve_finalize_blockers` or when prior rows are complete and finalize-only blockers remain.

The TUI SHALL avoid user-facing internal action names such as `run_review`, `run_verify_fixes`, and `resolve_finalize_blockers`. It SHALL map those internal actions to human wording such as `waiting`, `ready to finalize`, `waits for coverage`, `checked after review/findings`, or the relevant checklist title.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI active Finalize checklist row to follow status.next_required_action for known actions while retaining six checklist rows, data-grounded row details, and fallback derivation for missing or unknown actions. -->

#### Scenario: Run TUI follows next_required_action for verify fixes

**Given**: an active session status includes `coverage.stale > 0`
**And**: the same status includes fixed-pending-verification findings
**And**: the same status includes `next_required_action: run_verify_fixes`
**When**: the TUI renders the session snapshot
**Then**: the header identifies `Verify fixes` as the current checklist row
**And**: the Session summary identifies `Verify fixes` as the current checklist row
**And**: the Finalize checklist marks `Verify fixes` as the active row
**And**: the Review coverage row still shows stale or incomplete coverage detail
**And**: the rendered dashboard does not expose `run_verify_fixes` as raw text

#### Scenario: Run TUI maps status actions to checklist rows

**Given**: an active session status contains a known `next_required_action`
**When**: the TUI renders the session snapshot
**Then**: `run_review` selects Review coverage
**And**: `triage_findings` selects Triage findings
**And**: `fix_confirmed_findings` selects Fix confirmed findings
**And**: `run_verify_fixes` selects Verify fixes
**And**: `resolve_finalize_blockers` selects Final checks
**And**: `finalize` selects Finalize checkpoint
**And**: `cleanup_git_worktree` selects Finalize checkpoint
**And**: none of those internal action names are rendered as raw user-facing checklist labels

#### Scenario: Run TUI falls back for missing or unknown actions

**Given**: an active session status omits `next_required_action` or contains an unknown value
**When**: the TUI renders the session snapshot
**Then**: the current checklist row is derived from coverage, finding counts, blockers, finalization state, and failure state
**And**: existing fallback behavior for incomplete coverage, findings, final checks, finalization, and failure states is preserved
