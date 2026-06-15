# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUntypedBaseClass=false, reportUnknownParameterType=false
from __future__ import annotations

import importlib.util
from dataclasses import dataclass

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
        from textual.widgets import Static
    except ImportError as exc:
        raise RuntimeError(TUI_FALLBACK_WARNING) from exc

    class RunApp(App[dict[str, object]]):
        CSS = """
        Screen { layout: vertical; }
        #body { height: 1fr; padding: 1; }
        #progress_panel { border: heavy $accent; padding: 1; height: auto; }
        .panel { border: round $accent; padding: 1; height: auto; }
        #events { height: 1fr; }
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
            with Vertical(id="body"):
                yield Static(
                    progress_text(self.snapshot, activity_frame=self._activity_frame),
                    id="progress_panel",
                )
                with Horizontal():
                    yield Static(coverage_text(self.snapshot), id="coverage_panel", classes="panel")
                    yield Static(findings_text(self.snapshot), id="findings_panel", classes="panel")
                yield Static(_task_text(self.snapshot), id="task_panel", classes="panel")
                yield Static(_events_text(self.controller.events), id="events", classes="panel")
                yield Static(
                    "q stop after current step | r refresh | h help | Ctrl-C interrupt",
                    id="controls",
                )

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
            self.notify("q: stop after current step; r: refresh; Ctrl-C: interrupt")

        def refresh_view(self) -> None:
            self.snapshot = self.controller.snapshot()
            if self.snapshot.agent_status == "running":
                self._activity_frame += 1
            self.query_one("#progress_panel", Static).update(
                progress_text(self.snapshot, activity_frame=self._activity_frame)
            )
            self.query_one("#coverage_panel", Static).update(coverage_text(self.snapshot))
            self.query_one("#findings_panel", Static).update(findings_text(self.snapshot))
            self.query_one("#task_panel", Static).update(_task_text(self.snapshot))
            self.query_one("#events", Static).update(_events_text(self.controller.events))

    return RunApp(controller)


INCOMPLETE_COVERAGE_STATES = frozenset({"pending", "stale"})
EXCLUDED_COVERAGE_STATES = frozenset({"superseded"})
_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_BAR_WIDTH = 24


@dataclass(frozen=True)
class ProgressMetrics:
    completed: int
    total: int
    percent: int
    superseded: int
    incomplete: int


def calculate_progress_metrics(coverage: dict[str, object]) -> ProgressMetrics:
    total = 0
    completed = 0
    superseded = 0
    incomplete = 0
    for state, raw_count in coverage.items():
        count = _count_value(raw_count)
        if state in EXCLUDED_COVERAGE_STATES:
            superseded += count
            continue
        total += count
        if state in INCOMPLETE_COVERAGE_STATES:
            incomplete += count
        else:
            completed += count
    percent = round((completed / total) * 100) if total else 0
    return ProgressMetrics(
        completed=completed,
        total=total,
        percent=percent,
        superseded=superseded,
        incomplete=incomplete,
    )


def format_elapsed_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def progress_text(snapshot: RunSnapshot, *, activity_frame: int = 0) -> str:
    metrics = calculate_progress_metrics(snapshot.coverage)
    activity = agent_activity_text(snapshot.agent_status, activity_frame=activity_frame)
    progress_bar = _progress_bar(metrics.completed, metrics.total)
    summary = (
        f"{metrics.percent:3d}% {progress_bar} {metrics.completed}/{metrics.total} current cells"
    )
    run_state = (
        f"elapsed {format_elapsed_time(snapshot.elapsed_seconds)} | "
        f"step {snapshot.step} | agent {activity}"
    )
    remaining = (
        f"session {snapshot.session_id or 'none'} | remaining {metrics.incomplete} | "
        f"superseded {metrics.superseded}"
    )
    return "\n".join([summary, run_state, remaining])


def coverage_text(snapshot: RunSnapshot) -> str:
    if not snapshot.coverage:
        return "Coverage\n-"
    lines = ["Coverage"]
    for state, raw_count in sorted(snapshot.coverage.items()):
        count = _count_value(raw_count)
        marker = "!" if state in INCOMPLETE_COVERAGE_STATES else " "
        suffix = " remaining" if state in INCOMPLETE_COVERAGE_STATES else ""
        if state in EXCLUDED_COVERAGE_STATES:
            suffix = " excluded"
        lines.append(f"{marker} {state:<12} {_state_bar(count, snapshot.coverage)} {count}{suffix}")
    return "\n".join(lines)


def findings_text(snapshot: RunSnapshot) -> str:
    if not snapshot.findings:
        return "Findings\n-"
    chips = [
        f"[{state}:{_count_value(count)}]" for state, count in sorted(snapshot.findings.items())
    ]
    return "Findings\n" + " ".join(chips)


def _task_text(snapshot: RunSnapshot) -> str:
    prompt = _plain_text(snapshot.next_ready_prompt or "No ready task")
    argv = (
        " ".join(_plain_text(argument) for argument in snapshot.command_argv)
        if snapshot.command_argv
        else "n/a"
    )
    return f"Current task\n{prompt}\ncommand {argv}"


def agent_activity_text(agent_status: str, *, activity_frame: int = 0) -> str:
    if agent_status == "running":
        return f"{_SPINNER_FRAMES[activity_frame % len(_SPINNER_FRAMES)]} running"
    return f"· {_plain_text(agent_status)}"


def _plain_text(value: object) -> str:
    return "".join(_plain_character(character) for character in str(value)).replace("[", r"\[")


def _plain_character(character: str) -> str:
    if character in {"\n", "\t"} or (ord(character) >= 32 and ord(character) != 127):
        return character
    return "�"


def _agent_text(snapshot: RunSnapshot) -> str:
    argv = (
        " ".join(_plain_text(argument) for argument in snapshot.command_argv)
        if snapshot.command_argv
        else "n/a"
    )
    return (
        "Agent\n"
        f"status={_plain_text(snapshot.agent_status)} step={snapshot.step} "
        f"elapsed={snapshot.elapsed_seconds:.1f}s\nargv={argv}"
    )


def _events_text(events: tuple[RunEvent, ...]) -> str:
    lines = ["Events"]
    for event in events[-12:]:
        payload = " ".join(
            f"{_plain_text(key)}={_plain_text(value)}" for key, value in event.payload.items()
        )
        lines.append(f"{_plain_text(event.timestamp)} {_plain_text(event.type)} {payload}".rstrip())
    return "\n".join(lines)


def _progress_bar(completed: int, total: int) -> str:
    if total <= 0:
        return "[" + "·" * _BAR_WIDTH + "]"
    filled = round((completed / total) * _BAR_WIDTH)
    return "[" + "█" * filled + "░" * (_BAR_WIDTH - filled) + "]"


def _state_bar(count: int, all_counts: dict[str, object]) -> str:
    total = sum(_count_value(value) for value in all_counts.values())
    if total <= 0:
        return "·" * 6
    width = max(1, round((count / total) * 6)) if count else 0
    return "■" * width + "·" * (6 - width)


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    return 0


def _counts_text(counts: dict[str, object]) -> str:
    if not counts:
        return "-"
    return "\n".join(
        f"{_plain_text(key)}: {_plain_text(value)}" for key, value in sorted(counts.items())
    )
