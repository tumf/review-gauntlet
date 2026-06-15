# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUntypedBaseClass=false, reportUnknownParameterType=false
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from datetime import datetime

from review_gauntlet.run_controller import AgentOutputEntry, RunController, RunEvent, RunSnapshot

TUI_FALLBACK_WARNING = "TUI support is not installed; falling back to text mode."
TUI_INSTALL_GUIDANCE = 'Install with: uv tool install "review-gauntlet[tui]"'


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

    class RunApp(App[dict[str, object]]):
        CSS = """
        Screen { layout: vertical; }
        #body { height: 1fr; padding: 1; }
        #session_header { border: round $primary; padding: 1; height: auto; }
        #summary { height: auto; }
        #agent_panel { width: 1fr; }
        #session_panel { width: 1fr; }
        .panel { border: round $surface-lighten-2; padding: 1; height: auto; }
        .panel-active { border: round $success; }
        .panel-blocked { border: round $warning; }
        .panel-failed { border: round $error; }
        .panel-finalized { border: round $success; }
        #activity_timeline { height: 1fr; }
        #controls { color: $text-muted; height: auto; }        """
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
            self._completed_result: dict[str, object] | None = None

        def compose(self) -> ComposeResult:
            view = dashboard_state(
                self.snapshot, self.controller.events, activity_frame=self._activity_frame
            )
            with Vertical(id="body"):
                yield Static(header_text(view), id="session_header", classes=view.state_class)
                yield Static(
                    finalize_path_text(view),
                    id="finalize_path",
                    classes=f"panel {view.state_class}",
                )
                with Horizontal(id="summary"):
                    yield Static(agent_summary_text(view), id="agent_panel", classes="panel")
                    yield Static(session_summary_text(view), id="session_panel", classes="panel")
                yield Static(activity_text(view), id="activity_timeline", classes="panel")
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
            try:
                session_header = self.query_one("#session_header", Static)
                finalize_path = self.query_one("#finalize_path", Static)
                agent_panel = self.query_one("#agent_panel", Static)
                session_panel = self.query_one("#session_panel", Static)
                activity_timeline = self.query_one("#activity_timeline", Static)
            except NoMatches:
                return
            session_header.update(header_text(view))
            for state_class in (
                "panel",
                "panel-active",
                "panel-blocked",
                "panel-failed",
                "panel-finalized",
            ):
                session_header.set_class(state_class == view.state_class, state_class)
            finalize_path.update(finalize_path_text(view))
            agent_panel.update(agent_summary_text(view))
            session_panel.update(session_summary_text(view))
            activity_timeline.update(activity_text(view))

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
class FinalizeGate:
    index: int
    title: str
    state: str
    detail: str


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
    percent = round((displayed_completed / total) * 100) if total else 0
    return ProgressMetrics(
        displayed_completed, total, percent, superseded, pending + stale, pending, stale
    )


def format_elapsed_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


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
        return _summarize_text(" ".join(snapshot.command_argv), limit=80)
    if snapshot.agent_status == "running":
        return "command resolving..."
    return None


def dashboard_state(
    snapshot: RunSnapshot, events: tuple[RunEvent, ...], *, activity_frame: int = 0
) -> RunViewState:
    status_summary, state_class = terminal_state(snapshot.agent_status)
    command_label = format_command_label(snapshot)
    gates = derive_finalize_gates(snapshot)
    active_gate = next(
        (gate for gate in gates if gate.state in {"running", "blocked", "failed", "next"}),
        gates[-1],
    )
    timeline_events = tuple(format_activity_event(event) for event in events[-10:])
    output_events = tuple(
        format_agent_output_entry(entry) for entry in snapshot.agent_lifecycle.output_tail[-6:]
    )
    liveness_detail = agent_liveness_detail(snapshot)
    heartbeat_events = heartbeat_timeline_events(snapshot, activity_frame=activity_frame)
    coverage = calculate_progress_metrics(snapshot.coverage)
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
        open_findings=_count_value(snapshot.findings.get("open", 0)),
        task=task,
        command_label=command_label,
        agent_summary=build_agent_summary(snapshot, command_label, liveness_detail, artifact_path),
        session_summary=build_session_summary(snapshot, coverage, active_gate),
        timeline_events=timeline_events + heartbeat_events + output_events,
        activity=agent_activity_text(
            _display_agent_status(snapshot), activity_frame=activity_frame
        ),
        liveness_detail=liveness_detail,
        artifact_path=artifact_path,
        elapsed=format_elapsed_time(snapshot.elapsed_seconds),
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
    timeout = "timeout not set"
    if lifecycle.timeout_remaining_seconds is not None:
        timeout = f"timeout in {format_duration(lifecycle.timeout_remaining_seconds)}"
    artifact = short_artifact_path(artifact_path) if artifact_path is not None else None
    return AgentSummary(
        command=command_label or "command resolving...",
        status=liveness_detail,
        output=output,
        timeout=timeout,
        artifact=artifact,
    )


def build_session_summary(
    snapshot: RunSnapshot, coverage: ProgressMetrics, active_gate: FinalizeGate
) -> SessionSummary:
    return SessionSummary(
        coverage=f"{coverage.percent}%   {coverage.completed} / {coverage.total}",
        findings=f"open {_count_value(snapshot.findings.get('open', 0))}",
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


def derive_finalize_gates(snapshot: RunSnapshot) -> tuple[FinalizeGate, ...]:
    coverage = calculate_progress_metrics(snapshot.coverage)
    findings = snapshot.findings
    triage_count = _count_value(findings.get("untriaged", 0)) + _count_value(
        findings.get("reopened", 0)
    )
    fix_count = _count_value(findings.get("confirmed", 0))
    verify_count = _count_value(findings.get("fixed_pending_verification", 0))
    blockers = classify_finalize_blockers(snapshot.finalize_blockers)
    failed = snapshot.agent_status in {"failed", "interrupted", "timed_out", "cancelled"}
    finalized = snapshot.agent_status == "finalized" or snapshot.session_state == "finalized"

    review_state = "done" if coverage.incomplete == 0 else "running"
    review_detail = (
        f"{coverage.completed} / {coverage.total} reviewed, {coverage.incomplete} pending"
    )
    triage_state = "next" if review_state != "done" else ("running" if triage_count else "done")
    triage_detail = (
        "waits for coverage"
        if review_state != "done"
        else _count_detail(triage_count, "finding needs triage", "no findings need triage")
    )
    fix_state = "next" if triage_state != "done" else ("running" if fix_count else "done")
    fix_detail = (
        "no confirmed findings yet"
        if triage_state != "done"
        else _count_detail(fix_count, "confirmed finding needs fix", "no confirmed findings")
    )
    verify_state = "next" if fix_state != "done" else ("running" if verify_count else "done")
    verify_detail = (
        "no fixed-pending findings yet"
        if fix_state != "done"
        else _count_detail(
            verify_count, "fixed-pending finding needs verification", "no fixes need verification"
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
    if failed:
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


def heartbeat_timeline_events(
    snapshot: RunSnapshot, *, activity_frame: int = 0
) -> tuple[TimelineEvent, ...]:
    display_status = _display_agent_status(snapshot)
    if display_status != "quiet":
        return ()
    quiet_for = snapshot.agent_lifecycle.last_output_age_seconds
    detail = (
        f"agent alive no output for {format_duration(quiet_for)}"
        if quiet_for is not None
        else "agent alive no output yet"
    )
    if activity_frame % 4 != 0:
        return ()
    return (TimelineEvent("--:--:--", "event", detail),)


def format_duration(seconds: float) -> str:
    safe_seconds = max(0, int(seconds))
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
    if status in {"failed", "interrupted"}:
        return "FAILED", "panel-failed"
    if status in {"finalized", "completed"}:
        return "FINALIZED", "panel-finalized"
    return f"READY {status}", "panel"


def header_text(view: RunViewState) -> str:
    timeout = view.agent_summary.timeout.replace("timeout in ", "timeout ")
    return (
        "Review Gauntlet\n"
        f"{view.status_summary} · {view.gate_label} · {view.active_gate.title}\n"
        f"session {view.session_short_id} · agent {view.agent_name} · "
        f"{view.liveness_detail} · {timeout}"
    )


def progress_text(snapshot: RunSnapshot, *, activity_frame: int = 0) -> str:
    return header_text(dashboard_state(snapshot, (), activity_frame=activity_frame))


def finalize_path_text(view: RunViewState) -> str:
    lines = ["Next to finalize"]
    for gate in view.gates:
        marker = {"done": "✓", "running": "▶", "blocked": "!", "failed": "×"}.get(gate.state, " ")
        lines.append(f"{marker} {gate.title:<24} {gate.state:<7} {gate.detail}")
    return "\n".join(lines)


def coverage_text(snapshot: RunSnapshot) -> str:
    metrics = calculate_progress_metrics(snapshot.coverage)
    return "\n".join(
        [
            "Coverage",
            f"{metrics.percent:3d}% {_progress_bar(metrics.completed, metrics.total)}",
            f"reviewed / total cells: {metrics.completed} / {metrics.total}",
            (
                f"reviewed {metrics.completed} | pending {metrics.pending} | "
                f"stale {metrics.stale} | superseded {metrics.superseded}"
            ),
        ]
    )


def findings_text(snapshot: RunSnapshot) -> str:
    parts: list[str] = []
    for state in FINDING_STATES:
        label = state.replace("fixed_pending_verification", "fixed-pending")
        parts.append(f"{label} {_count_value(snapshot.findings.get(state, 0))}")
    return "Findings\n" + " | ".join(parts)


def agent_summary_text(view: RunViewState) -> str:
    lines = [
        "Agent",
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
            "Session",
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
    return f"· {_plain_text(agent_status)}"


def format_agent_output_entry(entry: AgentOutputEntry) -> TimelineEvent:
    label = "stderr" if entry.stream == "stderr" else "stdout"
    return TimelineEvent("--:--:--", label, sanitize_agent_output_line(entry.text))


def sanitize_agent_output_line(value: object, *, limit: int = 120) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    text = text.replace("\r", "\n")
    text = " ".join(_plain_text(text).split())
    text = re.sub(r"\b[A-Z0-9_]*(?:TOKEN|SECRET|KEY)=\S+", "<redacted>", text)
    return _summarize_text(text, limit=limit)


def format_activity_event(event: RunEvent) -> TimelineEvent:
    label = "event"
    detail = _event_label(event)
    event_detail = _event_detail(event)
    if event_detail:
        detail = f"{detail} {event_detail}"
    return TimelineEvent(format_event_time(event.timestamp), label, detail)


def activity_text(view: RunViewState) -> str:
    lines = ["Activity"]
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
        return format_task_title(str(event.payload.get("prompt", ""))).title
    if event.type == "agent_started":
        label = event.payload.get("command_label")
        return _summarize_text(label, limit=64) if label is not None else "command resolving..."
    if event.type == "failed":
        return _summarize_text(event.payload.get("reason", "command failed"), limit=64)
    return ""


def _agent_text(snapshot: RunSnapshot) -> str:  # pyright: ignore[reportUnusedFunction]
    command = format_command_label(snapshot) or "command resolving..."
    return (
        "Agent\n"
        f"status={_plain_text(snapshot.agent_status)} step={snapshot.step} "
        f"elapsed={snapshot.elapsed_seconds:.1f}s\ncommand={command}"
    )


def _plain_text(value: object) -> str:
    return "".join(_plain_character(character) for character in str(value)).replace("[", r"\[")


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


def _count_detail(count: int, singular: str, zero: str) -> str:
    if count == 0:
        return zero
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and not value.is_integer():
        return 0
    if isinstance(value, float):
        return max(0, int(value))
    return 0
