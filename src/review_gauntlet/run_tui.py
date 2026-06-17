# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUntypedBaseClass=false, reportUnknownParameterType=false
from __future__ import annotations

import importlib.util
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from review_gauntlet.__about__ import __version__
from review_gauntlet.run_controller import AgentOutputEntry, RunController, RunEvent, RunSnapshot

TUI_FALLBACK_WARNING = "TUI support is not installed; falling back to text mode."
TUI_INSTALL_GUIDANCE = "Reinstall review-gauntlet to restore bundled TUI dependencies."
PANEL_TITLES = {
    "header": "Review Gauntlet",
    "finalize_path": "Finalize checklist",
    "agent": "Agent",
    "session": "Session",
    "activity": "Activity",
}


def textual_available() -> bool:
    return (
        importlib.util.find_spec("rich") is not None
        and importlib.util.find_spec("textual") is not None
    )


def should_use_tui(*, output_format: str, no_tui: bool, stdout_is_tty: bool) -> bool:
    return output_format == "text" and not no_tui and stdout_is_tty


def create_run_app(controller: RunController) -> object:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.css.query import NoMatches
        from textual.widgets import Static
    except ImportError as exc:
        raise RuntimeError(TUI_FALLBACK_WARNING) from exc

    def titled_panel(
        title: str, body: Static, *, id: str | None = None, classes: str = "panel"
    ) -> Vertical:
        panel = Vertical(body, id=id, classes=classes)
        panel.border_title = title
        return panel

    class RunApp(App[dict[str, object]]):
        CSS = """
        $brand: #d97757;
        $dashboard-bg: #0f1117;
        $dashboard-surface: #151923;
        $dashboard-surface-muted: #11151d;
        Screen { layout: vertical; background: $dashboard-bg; }
        #body { height: 1fr; padding: 1; background: $dashboard-bg; }
        #session_header {
            border: round $primary;
            border-title-color: $brand;
            border-title-style: bold;
            padding: 1;
            height: auto;
            background: $dashboard-surface;
        }
        #header_status { text-style: bold; }
        #header_meta { color: $text-muted; }
        .panel-active #header_status { color: $success; }
        .panel-blocked #header_status { color: $warning; }
        .panel-failed #header_status { color: $error; }
        .panel-finalized #header_status { color: $success; }
        #summary { height: auto; }
        #agent_panel_container, #session_panel_container {
            width: 1fr;
        }
        #agent_panel_container { height: auto; }
        #session_panel_container { height: 100%; }
        .panel {
            border: round $surface-lighten-2;
            border-title-color: $text-muted;
            border-title-style: bold;
            padding: 1;
            height: auto;
            background: $dashboard-surface;
        }
        .panel-active { border: round $success; border-title-color: $success; }
        .panel-blocked { border: round $warning; border-title-color: $warning; }
        .panel-failed { border: round $error; border-title-color: $error; }
        .panel-finalized { border: round $success; border-title-color: $success; }
        #activity_panel { height: 1fr; }
        #activity_timeline { height: 1fr; }
        #controls {
            color: $text-muted;
            height: auto;
            background: $dashboard-surface-muted;
        }        """
        BINDINGS = [
            ("q", "stop_after_current_step", "Stop after current step"),
            ("ctrl+c", "interrupt", "Interrupt"),
            ("r", "refresh", "Refresh"),
            ("h", "help", "Help"),
        ]

        def __init__(self, run_controller: RunController) -> None:
            super().__init__()
            self.controller = run_controller
            self.snapshot = run_controller.snapshot()
            self._activity_frame = 0
            self._tui_render_state = empty_tui_render_state()
            self._completed_result: dict[str, object] | None = None

        def compose(self) -> ComposeResult:
            view = dashboard_state(
                self.snapshot, self.controller.events, activity_frame=self._activity_frame
            )
            with Vertical(id="body"):
                session_header = Vertical(id="session_header", classes=view.state_class)
                session_header.border_title = header_title_text()
                with session_header:
                    yield Static(header_status_text(view), id="header_status")
                    yield Static(header_meta_text(view), id="header_meta")
                yield titled_panel(
                    PANEL_TITLES["finalize_path"],
                    Static(finalize_path_text(view), id="finalize_path"),
                    id="finalize_path_panel",
                    classes=f"panel {view.state_class}",
                )
                with Horizontal(id="summary"):
                    yield titled_panel(
                        PANEL_TITLES["agent"],
                        Static(agent_summary_text(view), id="agent_panel"),
                        id="agent_panel_container",
                    )
                    yield titled_panel(
                        PANEL_TITLES["session"],
                        Static(session_summary_text(view), id="session_panel"),
                        id="session_panel_container",
                    )
                yield titled_panel(
                    PANEL_TITLES["activity"],
                    Static(activity_text(view), id="activity_timeline"),
                    id="activity_panel",
                )
                yield Static(footer_text(), id="controls")

        def on_mount(self) -> None:
            self.refresh_view()
            self.set_interval(0.25, self.refresh_view)
            self.run_worker(self._run_controller, thread=True)

        def _run_controller(self) -> None:
            result = self.controller.run()
            self._completed_result = result
            self.call_from_thread(self.refresh_view)

        def action_stop_after_current_step(self) -> None:
            if self._completed_result is not None:
                self.exit(self._completed_result)
                return
            self.controller.request_stop_after_current_step()
            self.refresh_view()

        def action_interrupt(self) -> None:
            if self._completed_result is not None:
                self.exit(self._completed_result)
                return
            self.controller.interrupt()
            self.exit({"completed": False, "reason": "interrupted", "steps": [], "step_count": 0})

        def action_refresh(self) -> None:
            self.snapshot = self.controller.refresh()
            self.refresh_view()

        def action_help(self) -> None:
            self.notify(footer_text())

        def refresh_view(self) -> None:
            self.snapshot = self.controller.snapshot()
            if self.snapshot.agent_status == "running":
                self._activity_frame += 1
            view = dashboard_state(
                self.snapshot, self.controller.events, activity_frame=self._activity_frame
            )
            sections = tui_render_sections(view)
            self._tui_render_state = update_tui_render_state(
                self._tui_render_state, tuple(sections.values())
            )
            flashes = self._tui_render_state.flashes
            try:
                session_header = self.query_one("#session_header", Vertical)
                header_status = self.query_one("#header_status", Static)
                header_meta = self.query_one("#header_meta", Static)
                finalize_path_panel = self.query_one("#finalize_path_panel", Vertical)
                finalize_path = self.query_one("#finalize_path", Static)
                agent_panel_container = self.query_one("#agent_panel_container", Vertical)
                session_panel_container = self.query_one("#session_panel_container", Vertical)
                agent_panel = self.query_one("#agent_panel", Static)
                session_panel = self.query_one("#session_panel", Static)
                activity_panel = self.query_one("#activity_panel", Vertical)
                activity_timeline = self.query_one("#activity_timeline", Static)
            except NoMatches:
                return
            header_status.update(render_tui_lines(sections["header_status"], flashes, mode="rich"))
            header_meta.update(render_tui_lines(sections["header_meta"], flashes, mode="rich"))
            for state_class in (
                "panel",
                "panel-active",
                "panel-blocked",
                "panel-failed",
                "panel-finalized",
            ):
                enabled = state_class == "panel" or state_class == view.state_class
                session_header.set_class(state_class == view.state_class, state_class)
                finalize_path_panel.set_class(enabled, state_class)
                agent_panel_container.set_class(enabled, state_class)
                session_panel_container.set_class(enabled, state_class)
                activity_panel.set_class(enabled, state_class)
            finalize_path.update(render_tui_lines(sections["finalize_path"], flashes, mode="rich"))
            agent_panel.update(render_tui_lines(sections["agent"], flashes, mode="rich"))
            session_panel.update(render_tui_lines(sections["session"], flashes, mode="rich"))
            activity_timeline.update(render_tui_lines(sections["activity"], flashes, mode="rich"))

    return RunApp(controller)


COMPLETED_COVERAGE_STATES = frozenset({"covered", "reviewed", "done"})
INCOMPLETE_COVERAGE_STATES = frozenset({"pending", "stale"})
EXCLUDED_COVERAGE_STATES = frozenset({"superseded"})
FINDING_STATES = (
    "open",
    "untriaged",
    "confirmed",
    "reopened",
    "fixed_pending_verification",
    "closed",
)
_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_BAR_WIDTH = 24
_FLASH_STYLE = "bold #fef3c7 on #3f3520"
_FLASH_DURATION_SECONDS = 0.9
_FIELD_RENDER_MODE = Literal["plain", "rich"]
_FAILED_AGENT_STATUSES = frozenset(
    {
        "failed",
        "timed_out",
        "command_failed",
        "startup_error",
        "template_error",
        "interrupted",
        "cancelled",
        "max_steps_exhausted",
    }
)
_AGENT_STATUS_LABELS = {
    "idle": "idle",
    "running": "running",
    "starting": "starting",
    "quiet": "quiet but alive",
    "completed": "completed",
    "timed_out": "timed out",
    "command_failed": "command failed",
    "startup_error": "startup error",
    "template_error": "template error",
    "interrupted": "interrupted",
    "cancelled": "interrupted",
    "max_steps_exhausted": "max steps exhausted",
    "failed": "failed",
}
_NEXT_ACTION_GATE_INDEX = {
    "run_review": 1,
    "triage_findings": 2,
    "fix_confirmed_findings": 3,
    "run_verify_fixes": 4,
    "resolve_finalize_blockers": 5,
    "finalize": 6,
}


@dataclass(frozen=True)
class ProgressMetrics:
    completed: int
    total: int
    percent: int
    superseded: int
    incomplete: int
    pending: int = 0
    stale: int = 0


@dataclass(frozen=True)
class TaskDisplay:
    title: str
    description: str


@dataclass(frozen=True)
class TimelineEvent:
    time: str
    label: str
    detail: str


@dataclass(frozen=True)
class AgentSummary:
    command: str
    status: str
    output: str
    timeout: str
    artifact: str | None


@dataclass(frozen=True)
class SessionSummary:
    coverage: str
    findings: str
    current: str
    agent_step: str


@dataclass(frozen=True)
class ActionableFindingSummary:
    open: int
    triage: int
    fix: int
    verify: int


@dataclass(frozen=True)
class FinalizeGate:
    index: int
    title: str
    state: str
    detail: str


@dataclass(frozen=True)
class TuiField:
    key: str
    display: str
    compare: object


@dataclass(frozen=True)
class TuiLine:
    fields: tuple[TuiField, ...]


@dataclass(frozen=True)
class TuiFlash:
    key: str
    expires_at: float


@dataclass(frozen=True)
class TuiRenderState:
    previous: dict[str, object]
    flashes: dict[str, TuiFlash]
    initialized: bool = False


def empty_tui_render_state() -> TuiRenderState:
    return TuiRenderState(previous={}, flashes={}, initialized=False)


@dataclass(frozen=True)
class RunViewState:
    status: str
    status_summary: str
    state_class: str
    session_short_id: str
    agent_name: str
    step_label: str
    gate_label: str
    active_gate: FinalizeGate
    gates: tuple[FinalizeGate, ...]
    coverage: ProgressMetrics
    open_findings: int
    task: TaskDisplay
    command_label: str | None
    agent_summary: AgentSummary
    session_summary: SessionSummary
    timeline_events: tuple[TimelineEvent, ...]
    activity: str
    liveness_detail: str
    artifact_path: str | None
    elapsed: str


def calculate_progress_metrics(coverage: dict[str, object]) -> ProgressMetrics:
    total = 0
    completed = 0
    superseded = 0
    pending = _count_value(coverage.get("pending", 0))
    stale = _count_value(coverage.get("stale", 0))
    for state, raw_count in coverage.items():
        count = _count_value(raw_count)
        if state in EXCLUDED_COVERAGE_STATES:
            superseded += count
            continue
        total += count
        if state in COMPLETED_COVERAGE_STATES:
            completed += count
    displayed_completed = min(completed, total)
    percent = int((displayed_completed / total) * 100) if total else 0
    return ProgressMetrics(
        displayed_completed, total, percent, superseded, pending + stale, pending, stale
    )


def actionable_finding_summary(findings: dict[str, object]) -> ActionableFindingSummary:
    triage = _count_value(findings.get("reopened", 0)) + _count_value(findings.get("untriaged", 0))
    fix = _count_value(findings.get("confirmed", 0))
    verify = _count_value(findings.get("fixed_pending_verification", 0))
    return ActionableFindingSummary(
        open=triage + fix + verify, triage=triage, fix=fix, verify=verify
    )


def format_elapsed_time(seconds: float) -> str:
    total_seconds = 0 if not math.isfinite(seconds) else max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def short_session_id(session_id: str | None) -> str:
    if not session_id:
        return "none"
    safe = _plain_text(session_id).replace("\n", " ")
    if len(safe) <= 12:
        return safe
    return f"{safe[:8]}…{safe[-4:]}"


def short_artifact_path(path: str) -> str:
    safe = _plain_text(path)
    marker = ".review-gauntlet/"
    if marker in safe:
        return marker + safe.rsplit(marker, maxsplit=1)[1]
    return _summarize_text(safe, limit=96)


def format_event_time(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except ValueError:
        return "--:--:--"


def format_task_title(prompt: str | None) -> TaskDisplay:
    if prompt is None or not prompt.strip():
        return TaskDisplay("WAITING FOR READY TASK", "No actionable ready prompt is available.")
    normalized = " ".join(prompt.lower().split())
    mappings = (
        (
            ("pending", "review"),
            "REVIEW PENDING CELLS",
            "Review cells that have not received coverage yet.",
        ),
        (("stale", "review"), "REVIEW STALE CELLS", "Refresh reviews whose coverage is stale."),
        (("untriaged",), "TRIAGE FINDINGS", "Classify open findings that still need triage."),
        (
            ("confirmed", "fix"),
            "FIX CONFIRMED FINDING",
            "Address confirmed findings with code changes.",
        ),
        (("fixed_pending",), "VERIFY FIXES", "Verify findings waiting for fix confirmation."),
        (("fixed-pending",), "VERIFY FIXES", "Verify findings waiting for fix confirmation."),
        (
            ("finalize",),
            "FINALIZE SESSION",
            "Finalize the review session when all required work is complete.",
        ),
    )
    for needles, title, description in mappings:
        if all(needle in normalized for needle in needles):
            return TaskDisplay(title, description)
    return TaskDisplay("READY TASK", _summarize_text(prompt, limit=96))


def format_command_label(snapshot: RunSnapshot) -> str | None:
    if snapshot.command_label:
        return _summarize_text(snapshot.command_label, limit=80)
    if snapshot.command_argv:
        return sanitize_agent_output_line(" ".join(snapshot.command_argv), limit=80)
    if snapshot.agent_status == "running":
        return "command resolving..."
    return None


def dashboard_state(
    snapshot: RunSnapshot, events: tuple[RunEvent, ...], *, activity_frame: int = 0
) -> RunViewState:
    status_summary, state_class = terminal_state(snapshot.agent_status)
    command_label = format_command_label(snapshot)
    gates = derive_finalize_gates(snapshot)
    active_gate = select_active_gate(snapshot, gates)
    timeline_events = tuple(format_activity_event(event) for event in events[-10:])
    output_events = tuple(
        format_agent_output_entry(entry) for entry in snapshot.agent_lifecycle.output_tail[-6:]
    )
    liveness_detail = agent_liveness_detail(snapshot)
    coverage = calculate_progress_metrics(snapshot.coverage)
    findings_summary = actionable_finding_summary(snapshot.findings)
    task = format_task_title(snapshot.next_ready_prompt)
    artifact_path = snapshot.agent_lifecycle.artifact_path
    return RunViewState(
        status=snapshot.agent_status,
        status_summary=status_summary,
        state_class=state_class,
        session_short_id=short_session_id(snapshot.session_id),
        agent_name=command_label or "agent idle",
        step_label=f"agent step {snapshot.step}",
        gate_label=f"gate {active_gate.index}/6",
        active_gate=active_gate,
        gates=gates,
        coverage=coverage,
        open_findings=findings_summary.open,
        task=task,
        command_label=command_label,
        agent_summary=build_agent_summary(snapshot, command_label, liveness_detail, artifact_path),
        session_summary=build_session_summary(snapshot, coverage, active_gate, findings_summary),
        timeline_events=timeline_events + output_events,
        activity=agent_activity_text(
            _display_agent_status(snapshot), activity_frame=activity_frame
        ),
        liveness_detail=liveness_detail,
        artifact_path=artifact_path,
        elapsed=format_elapsed_time(snapshot.elapsed_seconds),
    )


def select_active_gate(snapshot: RunSnapshot, gates: tuple[FinalizeGate, ...]) -> FinalizeGate:
    mapped_index = _NEXT_ACTION_GATE_INDEX.get(snapshot.next_required_action or "")
    if mapped_index is not None:
        return gates[mapped_index - 1]
    return next(
        (gate for gate in gates if gate.state in {"running", "blocked", "failed", "next"}),
        gates[-1],
    )


def build_agent_summary(
    snapshot: RunSnapshot,
    command_label: str | None,
    liveness_detail: str,
    artifact_path: str | None,
) -> AgentSummary:
    lifecycle = snapshot.agent_lifecycle
    output = "no output yet"
    if lifecycle.last_output_age_seconds is not None:
        output = f"last output {format_duration(lifecycle.last_output_age_seconds)} ago"
    timeout = "not configured"
    if lifecycle.timeout_remaining_seconds is not None:
        timeout = f"in {format_duration(lifecycle.timeout_remaining_seconds)}"
    elif lifecycle.timeout_seconds is not None:
        timeout = f"configured {format_duration(lifecycle.timeout_seconds)}"
    artifact = short_artifact_path(artifact_path) if artifact_path is not None else None
    return AgentSummary(
        command=command_label or "command resolving...",
        status=liveness_detail,
        output=output,
        timeout=timeout,
        artifact=artifact,
    )


def build_session_summary(
    snapshot: RunSnapshot,
    coverage: ProgressMetrics,
    active_gate: FinalizeGate,
    findings_summary: ActionableFindingSummary,
) -> SessionSummary:
    findings = f"open {findings_summary.open}"
    if findings_summary.open:
        findings = (
            f"{findings}   triage {findings_summary.triage} | "
            f"fix {findings_summary.fix} | verify {findings_summary.verify}"
        )
    return SessionSummary(
        coverage=f"{coverage.percent}%   {coverage.completed} / {coverage.total}",
        findings=findings,
        current=active_gate.title.lower(),
        agent_step=str(snapshot.step),
    )


@dataclass(frozen=True)
class BlockerGroups:
    coverage: tuple[str, ...]
    findings: tuple[str, ...]
    final_checks: tuple[str, ...]


def classify_finalize_blockers(blockers: tuple[str, ...]) -> BlockerGroups:
    coverage: list[str] = []
    findings: list[str] = []
    final_checks: list[str] = []
    for blocker in blockers:
        normalized = blocker.lower()
        if "review cells are still pending" in normalized or "review cells are stale" in normalized:
            coverage.append(blocker)
        elif any(
            needle in normalized
            for needle in (
                "untriaged",
                "reopened",
                "confirmed",
                "fixed-pending",
                "fixed_pending",
                "fixed findings require verification",
            )
        ):
            findings.append(blocker)
        else:
            final_checks.append(blocker)
    return BlockerGroups(tuple(coverage), tuple(findings), tuple(final_checks))


def _is_finalize_ready_timeout(snapshot: RunSnapshot) -> bool:
    return (
        snapshot.agent_status == "timed_out"
        and snapshot.can_finalize
        and not snapshot.finalize_blockers
    )


def derive_finalize_gates(snapshot: RunSnapshot) -> tuple[FinalizeGate, ...]:
    coverage = calculate_progress_metrics(snapshot.coverage)
    findings = snapshot.findings
    triage_count = _count_value(findings.get("untriaged", 0)) + _count_value(
        findings.get("reopened", 0)
    )
    fix_count = _count_value(findings.get("confirmed", 0))
    verify_count = _count_value(findings.get("fixed_pending_verification", 0))
    blockers = classify_finalize_blockers(snapshot.finalize_blockers)
    failed = snapshot.agent_status in _FAILED_AGENT_STATUSES
    finalized = snapshot.agent_status == "finalized" or snapshot.session_state == "finalized"

    review_state = "done" if coverage.incomplete == 0 else "running"
    review_detail = (
        f"{coverage.completed} / {coverage.total} reviewed, {coverage.incomplete} pending"
    )
    triage_state = "next" if review_state != "done" else ("running" if triage_count else "done")
    triage_detail = (
        "waits for coverage"
        if review_state != "done"
        else _count_detail(
            triage_count,
            "finding needs triage",
            "no findings need triage",
            plural="findings need triage",
        )
    )
    fix_state = "next" if triage_state != "done" else ("running" if fix_count else "done")
    fix_detail = (
        "no confirmed findings yet"
        if triage_state != "done"
        else _count_detail(
            fix_count,
            "confirmed finding needs fix",
            "no confirmed findings",
            plural="confirmed findings need fix",
        )
    )
    verify_state = "next" if fix_state != "done" else ("running" if verify_count else "done")
    verify_detail = (
        "no fixed-pending findings yet"
        if fix_state != "done"
        else _count_detail(
            verify_count,
            "fixed-pending finding needs verification",
            "no fixes need verification",
            plural="fixed-pending findings need verification",
        )
    )
    prior_done = all(
        state == "done" for state in (review_state, triage_state, fix_state, verify_state)
    )
    if not prior_done:
        final_checks_state = "later"
        final_checks_detail = "checked after review/findings"
    elif blockers.final_checks:
        final_checks_state = "blocked"
        final_checks_detail = _summarize_text(blockers.final_checks[0], limit=64)
    else:
        final_checks_state = "done"
        final_checks_detail = "ready"
    if finalized:
        checkpoint_state = "done"
        checkpoint_detail = "complete"
    elif _is_finalize_ready_timeout(snapshot):
        checkpoint_state = "running"
        checkpoint_detail = "agent timed out; run review-gauntlet finalize"
    elif final_checks_state == "done" and snapshot.can_finalize:
        checkpoint_state = "running"
        checkpoint_detail = "ready to finalize"
    else:
        checkpoint_state = "later"
        checkpoint_detail = "waiting"
    gates = [
        FinalizeGate(1, "Review coverage", review_state, review_detail),
        FinalizeGate(2, "Triage findings", triage_state, triage_detail),
        FinalizeGate(3, "Fix confirmed findings", fix_state, fix_detail),
        FinalizeGate(4, "Verify fixes", verify_state, verify_detail),
        FinalizeGate(5, "Final checks", final_checks_state, final_checks_detail),
        FinalizeGate(6, "Finalize checkpoint", checkpoint_state, checkpoint_detail),
    ]
    if finalized:
        return tuple(FinalizeGate(gate.index, gate.title, "done", "complete") for gate in gates)
    if failed and not _is_finalize_ready_timeout(snapshot):
        for gate in gates:
            if gate.state in {"running", "blocked", "next", "later"}:
                return tuple(
                    FinalizeGate(item.index, item.title, "failed", item.detail)
                    if item.index == gate.index
                    else item
                    for item in gates
                )
    return tuple(gates)


def _display_agent_status(snapshot: RunSnapshot) -> str:
    if snapshot.agent_status == "running" and snapshot.agent_lifecycle.status == "idle":
        return "running"
    return snapshot.agent_lifecycle.status or snapshot.agent_status


def agent_liveness_detail(snapshot: RunSnapshot) -> str:
    lifecycle = snapshot.agent_lifecycle
    display_status = _display_agent_status(snapshot)
    if display_status == "quiet":
        quiet_for = lifecycle.last_output_age_seconds
        if quiet_for is not None:
            return f"quiet {format_duration(quiet_for)}"
        return "quiet but alive"
    return agent_activity_text(display_status)


def format_duration(seconds: float) -> str:
    safe_seconds = 0 if not math.isfinite(seconds) else max(0, int(seconds))
    if safe_seconds < 60:
        return f"{safe_seconds}s"
    minutes, remainder = divmod(safe_seconds, 60)
    if minutes < 60:
        return f"{minutes}m{remainder:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def terminal_state(agent_status: str) -> tuple[str, str]:
    status = _plain_text(agent_status)
    if status == "running":
        return "RUNNING", "panel-active"
    if status == "blocked":
        return "BLOCKED", "panel-blocked"
    if status in _FAILED_AGENT_STATUSES:
        return _agent_terminal_label(status), "panel-failed"
    if status in {"finalized", "completed"}:
        return "FINALIZED", "panel-finalized"
    return f"READY {_agent_status_label(status).upper()}", "panel"


def _agent_terminal_label(status: str) -> str:
    if status == "timed_out":
        return "TIMED OUT"
    if status == "command_failed":
        return "COMMAND FAILED"
    if status == "startup_error":
        return "STARTUP ERROR"
    if status == "template_error":
        return "TEMPLATE ERROR"
    if status in {"interrupted", "cancelled"}:
        return "INTERRUPTED"
    if status == "max_steps_exhausted":
        return "MAX STEPS EXHAUSTED"
    return "FAILED"


def _agent_status_label(status: str) -> str:
    return _AGENT_STATUS_LABELS.get(status, status.replace("_", " "))


def header_title_text() -> str:
    return f"✻ Review Gauntlet v{__version__}"


def header_status_text(view: RunViewState) -> str:
    return f"{view.status_summary} · {view.gate_label} · {view.active_gate.title}"


def header_meta_text(view: RunViewState) -> str:
    return f"{view.session_short_id} · agent {view.agent_name} · {view.liveness_detail}"


def header_text(view: RunViewState) -> str:
    return "\n".join([header_title_text(), header_status_text(view), header_meta_text(view)])


def progress_text(snapshot: RunSnapshot, *, activity_frame: int = 0) -> str:
    return header_text(dashboard_state(snapshot, (), activity_frame=activity_frame))


def update_tui_render_state(
    state: TuiRenderState,
    sections: tuple[tuple[TuiLine, ...], ...],
    *,
    now: float | None = None,
    flash_duration_seconds: float = _FLASH_DURATION_SECONDS,
) -> TuiRenderState:
    current_time = time.monotonic() if now is None else now
    current = _field_compare_map(sections)
    flashes = {
        key: flash
        for key, flash in state.flashes.items()
        if flash.expires_at > current_time and key in current
    }
    if state.initialized:
        for key, value in current.items():
            if (key in state.previous and state.previous[key] != value) or (
                key not in state.previous and _is_activity_value_key(key)
            ):
                flashes[key] = TuiFlash(key=key, expires_at=current_time + flash_duration_seconds)
    return TuiRenderState(previous=current, flashes=flashes, initialized=True)


def tui_render_sections(view: RunViewState) -> dict[str, tuple[TuiLine, ...]]:
    return {
        "header_status": header_status_tui_lines(view),
        "header_meta": header_meta_tui_lines(view),
        "finalize_path": finalize_path_tui_lines(view),
        "agent": agent_summary_tui_lines(view),
        "session": session_summary_tui_lines(view),
        "activity": activity_tui_lines(view),
    }


def render_tui_lines(
    lines: tuple[TuiLine, ...],
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> Any:
    flash_keys = frozenset(flashes or {})
    if mode == "rich":
        from rich.text import Text

        rendered = Text()
        for line_index, line in enumerate(lines):
            if line_index:
                rendered.append("\n")
            for field in line.fields:
                style = _FLASH_STYLE if field.key in flash_keys else None
                rendered.append(field.display, style=style)
        return rendered
    return "\n".join("".join(field.display for field in line.fields) for line in lines)


def header_status_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    return (
        TuiLine(
            (
                _field("header.status.summary", view.status_summary),
                _literal(" · ", key="header.status.sep.1"),
                _field("header.status.gate", view.gate_label, compare=view.active_gate.index),
                _literal(" · ", key="header.status.sep.2"),
                _field("header.status.active_gate", view.active_gate.title),
            )
        ),
    )


def header_meta_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    return (
        TuiLine(
            (
                _field("header.meta.session", view.session_short_id),
                _literal(" · agent ", key="header.meta.agent_prefix"),
                _field("header.meta.agent", view.agent_name),
                _literal(" · ", key="header.meta.sep"),
                _field(
                    "header.meta.liveness",
                    view.liveness_detail,
                    compare=_semantic_liveness_compare(view.liveness_detail),
                ),
            )
        ),
    )


def finalize_path_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    lines: list[TuiLine] = []
    for gate in view.gates:
        marker = {"done": "✓", "running": "▶", "blocked": "!", "failed": "×"}.get(gate.state, " ")
        prefix = f"gate.{gate.index}"
        lines.append(
            TuiLine(
                (
                    _field(f"finalize.{prefix}.marker", marker),
                    _literal(" ", key=f"finalize.{prefix}.marker_space"),
                    _field(f"finalize.{prefix}.title", f"{gate.title:<24}", compare=gate.title),
                    _literal(" ", key=f"finalize.{prefix}.title_space"),
                    _field(f"finalize.{prefix}.state", f"{gate.state:<7}", compare=gate.state),
                    _literal(" ", key=f"finalize.{prefix}.state_space"),
                    _field(f"finalize.{prefix}.detail", gate.detail),
                )
            )
        )
    return tuple(lines)


def agent_summary_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    lines = [
        _label_value_line("agent.command", "command ", view.agent_summary.command),
        _label_value_line(
            "agent.status",
            "status  ",
            view.agent_summary.status,
            compare=_semantic_liveness_compare(view.agent_summary.status),
        ),
        _label_value_line(
            "agent.output",
            "output  ",
            view.agent_summary.output,
            compare=_agent_output_compare(view.agent_summary.output),
        ),
        _label_value_line(
            "agent.timeout",
            "timeout ",
            view.agent_summary.timeout,
            compare=_agent_timeout_compare(view.agent_summary.timeout),
        ),
    ]
    if view.agent_summary.artifact is not None:
        lines.append(_label_value_line("agent.artifact", "artifact ", view.agent_summary.artifact))
    return tuple(lines)


def session_summary_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    coverage = view.coverage
    return (
        TuiLine(
            (
                _literal("Coverage  ", key="session.coverage.label"),
                _field("session.coverage.percent", f"{coverage.percent}%", compare="derived"),
                _literal("   ", key="session.coverage.percent_sep"),
                _field(
                    "session.coverage.completed",
                    str(coverage.completed),
                    compare=coverage.completed,
                ),
                _literal(" / ", key="session.coverage.count_sep"),
                _field("session.coverage.total", str(coverage.total), compare=coverage.total),
            )
        ),
        TuiLine(
            (
                _literal("Findings  open ", key="session.findings.label"),
                _field(
                    "session.findings.open", str(view.open_findings), compare=view.open_findings
                ),
            )
        ),
        _label_value_line("session.current", "Current   ", view.session_summary.current),
        _label_value_line(
            "session.agent_step",
            "Agent step ",
            view.session_summary.agent_step,
            compare=view.session_summary.agent_step,
        ),
    )


def activity_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    if not view.timeline_events:
        return (TuiLine((_field("activity.empty", "--:--:-- waiting for run activity"),)),)
    lines: list[TuiLine] = []
    for event in view.timeline_events:
        identity = _activity_identity(event)
        suffix = f" - {event.detail}" if event.detail else ""
        lines.append(
            TuiLine(
                (
                    _field(f"activity.{identity}.time", event.time, compare="timestamp"),
                    _literal(" ", key=f"activity.{identity}.time_space"),
                    _field(f"activity.{identity}.label", event.label, compare=event.label),
                    _field(
                        f"activity.{identity}.detail", suffix, compare=(event.label, event.detail)
                    ),
                )
            )
        )
    return tuple(lines)


def finalize_path_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(finalize_path_tui_lines(view), flashes, mode=mode)


def agent_summary_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(agent_summary_tui_lines(view), flashes, mode=mode)


def session_summary_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(session_summary_tui_lines(view), flashes, mode=mode)


def activity_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(activity_tui_lines(view), flashes, mode=mode)


def _field(key: str, display: str, *, compare: object | None = None) -> TuiField:
    return TuiField(key=key, display=display, compare=display if compare is None else compare)


def _literal(display: str, *, key: str) -> TuiField:
    return TuiField(key=key, display=display, compare=display)


def _label_value_line(
    key: str, label: str, value: str, *, compare: object | None = None
) -> TuiLine:
    return TuiLine(
        (
            _literal(label, key=f"{key}.label"),
            _field(f"{key}.value", value, compare=value if compare is None else compare),
        )
    )


def _field_compare_map(sections: tuple[tuple[TuiLine, ...], ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for lines in sections:
        for line in lines:
            for field in line.fields:
                result[field.key] = field.compare
    return result


def _is_activity_value_key(key: str) -> bool:
    return key.startswith("activity.") and key.endswith(".detail")


def _semantic_liveness_compare(value: str) -> object:
    if value.startswith("quiet "):
        return ("quiet",)
    if value.startswith("last output "):
        return ("last_output",)
    return value


def _agent_output_compare(value: str) -> object:
    if value.startswith("last output "):
        return ("last_output",)
    return value


def _agent_timeout_compare(value: str) -> object:
    if value.startswith("in "):
        return ("countdown",)
    if value.startswith("configured "):
        return ("configured",)
    return value


def _activity_identity(event: TimelineEvent) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", f"{event.label}-{event.detail}").strip("-")
    if not normalized:
        return "empty"
    return normalized[:80]


def titled_section(title: str, body: str) -> str:
    return f"{title}\n{body}" if body else title


def compact_dashboard_text(snapshot: RunSnapshot, events: tuple[RunEvent, ...] = ()) -> str:
    view = dashboard_state(snapshot, events)
    return "\n".join(
        [
            header_text(view),
            titled_section(PANEL_TITLES["finalize_path"], finalize_path_text(view)),
            titled_section(PANEL_TITLES["agent"], agent_summary_text(view)),
            titled_section(PANEL_TITLES["session"], session_summary_text(view)),
            titled_section(PANEL_TITLES["activity"], activity_text(view)),
            footer_text(),
        ]
    )


def finalize_path_text(view: RunViewState) -> str:
    lines: list[str] = []
    for gate in view.gates:
        marker = {"done": "✓", "running": "▶", "blocked": "!", "failed": "×"}.get(gate.state, " ")
        lines.append(f"{marker} {gate.title:<24} {gate.state:<7} {gate.detail}")
    return "\n".join(lines)


def coverage_text(snapshot: RunSnapshot) -> str:
    metrics = calculate_progress_metrics(snapshot.coverage)
    return "\n".join(
        [
            f"{metrics.percent:3d}% {_progress_bar(metrics.completed, metrics.total)}",
            f"reviewed / total cells: {metrics.completed} / {metrics.total}",
            (
                f"reviewed {metrics.completed} | pending {metrics.pending} | "
                f"stale {metrics.stale} | superseded {metrics.superseded}"
            ),
        ]
    )


def findings_text(snapshot: RunSnapshot) -> str:
    summary = actionable_finding_summary(snapshot.findings)
    parts: list[str] = []
    for state in FINDING_STATES:
        label = state.replace("fixed_pending_verification", "fixed-pending")
        count = summary.open if state == "open" else _count_value(snapshot.findings.get(state, 0))
        parts.append(f"{label} {count}")
    return " | ".join(parts)


def agent_summary_text(view: RunViewState) -> str:
    lines = [
        f"command {view.agent_summary.command}",
        f"status  {view.agent_summary.status}",
        f"output  {view.agent_summary.output}",
        f"timeout {view.agent_summary.timeout}",
    ]
    if view.agent_summary.artifact is not None:
        lines.append(f"artifact {view.agent_summary.artifact}")
    return "\n".join(lines)


def session_summary_text(view: RunViewState) -> str:
    return "\n".join(
        [
            f"Coverage  {view.session_summary.coverage}",
            f"Findings  {view.session_summary.findings}",
            f"Current   {view.session_summary.current}",
            f"Agent step {view.session_summary.agent_step}",
        ]
    )


def current_operation_text(view: RunViewState) -> str:
    return agent_summary_text(view)


def _task_text(snapshot: RunSnapshot) -> str:  # pyright: ignore[reportUnusedFunction]
    return current_operation_text(dashboard_state(snapshot, ()))


def agent_activity_text(agent_status: str, *, activity_frame: int = 0) -> str:
    if agent_status in {"running", "starting"}:
        return f"{_SPINNER_FRAMES[activity_frame % len(_SPINNER_FRAMES)]} {agent_status}"
    if agent_status == "quiet":
        return "quiet but alive"
    return f"· {_agent_status_label(_plain_text(agent_status))}"


def format_agent_output_entry(entry: AgentOutputEntry) -> TimelineEvent:
    label = "stderr" if entry.stream == "stderr" else "stdout"
    return TimelineEvent("--:--:--", label, sanitize_agent_output_line(entry.text))


def sanitize_agent_output_line(value: object, *, limit: int = 120) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    text = text.replace("\r", "\n")
    text = " ".join(_plain_text(text).split())
    text = text[: limit * 4]
    secret_patterns = (
        r"\b[A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD)=\S+",
        r"\b(?:authorization|x-api-key)\s*:\s*\S+(?:\s+\S+)?",
        r"[\"']?\b(?:api[_-]?key|token|secret|password)\b[\"']?\s*[:=]\s*[\"']?\S+[\"']?",
    )
    for pattern in secret_patterns:
        text = re.sub(pattern, "<redacted>", text, flags=re.IGNORECASE)
    return _summarize_text(text, limit=limit)


def format_activity_event(event: RunEvent) -> TimelineEvent:
    label = "event"
    detail = _event_label(event)
    event_detail = _event_detail(event)
    if event_detail:
        detail = f"{detail} {event_detail}"
    return TimelineEvent(format_event_time(event.timestamp), label, detail)


def activity_text(view: RunViewState) -> str:
    lines: list[str] = []
    if not view.timeline_events:
        lines.append("--:--:-- waiting for run activity")
    for event in view.timeline_events:
        suffix = f" - {event.detail}" if event.detail else ""
        lines.append(f"{event.time} {event.label}{suffix}")
    return "\n".join(lines)


def _events_text(events: tuple[RunEvent, ...]) -> str:  # pyright: ignore[reportUnusedFunction]
    empty = RunSnapshot(None, {}, {}, None, 0, "idle", (), 0)
    return activity_text(dashboard_state(empty, events))


def footer_text() -> str:
    return "q stop after current step | r refresh | h help | Ctrl-C interrupt"


def _event_label(event: RunEvent) -> str:
    if event.type == "run_started":
        return "run started"
    if event.type == "status_refreshed":
        return "status refreshed"
    if event.type == "step_started":
        return f"step {_plain_text(event.payload.get('step', '?'))} started"
    if event.type == "agent_started":
        return "agent started"
    if event.type == "blocked":
        return "blocked"
    if event.type == "failed":
        return "failed"
    if event.type == "finalized":
        return "finalized"
    return _plain_text(event.type).replace("_", " ")


def _event_detail(event: RunEvent) -> str:
    if event.type in {"run_started", "status_refreshed", "blocked", "finalized"}:
        session_id = event.payload.get("session_id")
        reason = event.payload.get("reason")
        parts: list[str] = []
        if session_id is not None:
            parts.append(f"session {short_session_id(str(session_id))}")
        if reason is not None:
            parts.append(_summarize_text(reason, limit=48))
        return "; ".join(parts)
    if event.type == "step_started":
        return format_task_title(str(event.payload.get("prompt") or "")).title
    if event.type == "agent_started":
        label = event.payload.get("command_label")
        return _summarize_text(label, limit=64) if label is not None else "command resolving..."
    if event.type == "failed":
        return _summarize_text(event.payload.get("reason") or "command failed", limit=64)
    return ""


def _agent_text(snapshot: RunSnapshot) -> str:  # pyright: ignore[reportUnusedFunction]
    command = format_command_label(snapshot) or "command resolving..."
    return (
        "Agent\n"
        f"status={_plain_text(snapshot.agent_status)} step={snapshot.step} "
        f"elapsed={snapshot.elapsed_seconds:.1f}s\ncommand={command}"
    )


def _plain_text(value: object) -> str:
    return "".join(_plain_character(character) for character in str(value))


def _plain_character(character: str) -> str:
    if character in {"\n", "\r", "\t"}:
        return " "
    if ord(character) >= 32 and ord(character) != 127:
        return character
    return "�"


def _summarize_text(value: object, *, limit: int) -> str:
    text = " ".join(_plain_text(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)]}…"


def _progress_bar(completed: int, total: int) -> str:
    if total <= 0:
        return "[" + "·" * _BAR_WIDTH + "]"
    filled = min(_BAR_WIDTH, max(0, round((completed / total) * _BAR_WIDTH)))
    return "[" + "█" * filled + "░" * (_BAR_WIDTH - filled) + "]"


def _count_detail(count: int, singular: str, zero: str, *, plural: str | None = None) -> str:
    if count == 0:
        return zero
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural}" if plural is not None else f"{count} {singular}s"


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and not value.is_integer():
        return 0
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value))
        except (ValueError, OverflowError):
            return 0
    return 0
