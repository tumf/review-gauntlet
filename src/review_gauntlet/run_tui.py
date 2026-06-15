# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUntypedBaseClass=false, reportUnknownParameterType=false
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from datetime import datetime

from review_gauntlet.run_controller import RunController, RunEvent, RunSnapshot

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
        #metrics { height: auto; }
        .panel { border: round $surface-lighten-2; padding: 1; height: auto; }
        .panel-active { border: round $success; }
        .panel-blocked { border: round $warning; }
        .panel-failed { border: round $error; }
        .panel-finalized { border: round $success; }
        #activity_timeline { height: 1fr; }
        #controls { color: $text-muted; height: auto; }
        """
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

        def compose(self) -> ComposeResult:
            view = dashboard_state(
                self.snapshot, self.controller.events, activity_frame=self._activity_frame
            )
            with Vertical(id="body"):
                yield Static(header_text(view), id="session_header", classes=view.state_class)
                with Horizontal(id="metrics"):
                    yield Static(coverage_text(self.snapshot), id="coverage_panel", classes="panel")
                    yield Static(findings_text(self.snapshot), id="findings_panel", classes="panel")
                yield Static(
                    current_operation_text(view),
                    id="task_panel",
                    classes=f"panel {view.state_class}",
                )
                yield Static(activity_text(view), id="activity_timeline", classes="panel")
                yield Static(footer_text(), id="controls")

        def on_mount(self) -> None:
            self.refresh_view()
            self.set_interval(0.25, self.refresh_view)
            self.run_worker(self._run_controller, thread=True)

        def _run_controller(self) -> None:
            result = self.controller.run()
            self.call_from_thread(self.exit, result)

        def action_stop_after_current_step(self) -> None:
            self.controller.request_stop_after_current_step()
            self.refresh_view()

        def action_interrupt(self) -> None:
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
                coverage_panel = self.query_one("#coverage_panel", Static)
                findings_panel = self.query_one("#findings_panel", Static)
                task_panel = self.query_one("#task_panel", Static)
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
            coverage_panel.update(coverage_text(self.snapshot))
            findings_panel.update(findings_text(self.snapshot))
            task_panel.update(current_operation_text(view))
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
class RunViewState:
    status: str
    status_summary: str
    state_class: str
    session_short_id: str
    agent_name: str
    step_label: str
    coverage: ProgressMetrics
    open_findings: int
    task: TaskDisplay
    command_label: str | None
    timeline_events: tuple[TimelineEvent, ...]
    activity: str
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
    return RunViewState(
        status=snapshot.agent_status,
        status_summary=status_summary,
        state_class=state_class,
        session_short_id=short_session_id(snapshot.session_id),
        agent_name=command_label or "agent idle",
        step_label=f"step {snapshot.step}",
        coverage=calculate_progress_metrics(snapshot.coverage),
        open_findings=_count_value(snapshot.findings.get("open", 0)),
        task=format_task_title(snapshot.next_ready_prompt),
        command_label=command_label,
        timeline_events=tuple(format_activity_event(event) for event in events[-12:]),
        activity=agent_activity_text(snapshot.agent_status, activity_frame=activity_frame),
        elapsed=format_elapsed_time(snapshot.elapsed_seconds),
    )


def terminal_state(agent_status: str) -> tuple[str, str]:
    status = _plain_text(agent_status)
    if status == "running":
        return "RUNNING - agent is working", "panel-active"
    if status == "blocked":
        return "BLOCKED - human attention needed", "panel-blocked"
    if status in {"failed", "interrupted"}:
        return "FAILED - run stopped before completion", "panel-failed"
    if status in {"finalized", "completed"}:
        return "FINALIZED - review session complete", "panel-finalized"
    return f"READY - {status}", "panel"


def header_text(view: RunViewState) -> str:
    return (
        f"Review dashboard | session {view.session_short_id} | {view.status_summary}\n"
        f"{view.step_label} | elapsed {view.elapsed} | agent {view.activity}"
    )


def progress_text(snapshot: RunSnapshot, *, activity_frame: int = 0) -> str:
    return header_text(dashboard_state(snapshot, (), activity_frame=activity_frame))


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


def current_operation_text(view: RunViewState) -> str:
    lines = ["Current operation", view.task.title, view.task.description]
    if view.command_label is not None:
        lines.append(f"command {view.command_label}")
    return "\n".join(lines)


def _task_text(snapshot: RunSnapshot) -> str:  # pyright: ignore[reportUnusedFunction]
    return current_operation_text(dashboard_state(snapshot, ()))


def agent_activity_text(agent_status: str, *, activity_frame: int = 0) -> str:
    if agent_status == "running":
        return f"{_SPINNER_FRAMES[activity_frame % len(_SPINNER_FRAMES)]} running"
    return f"· {_plain_text(agent_status)}"


def format_activity_event(event: RunEvent) -> TimelineEvent:
    label = _event_label(event)
    detail = _event_detail(event)
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
