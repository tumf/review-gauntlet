# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUntypedBaseClass=false, reportUnknownParameterType=false
from __future__ import annotations

import importlib.util

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
        from textual.widgets import Footer, Header, Static
    except ImportError as exc:
        raise RuntimeError(TUI_FALLBACK_WARNING) from exc

    class RunApp(App[dict[str, object]]):
        CSS = """
        Screen { layout: vertical; }
        #body { height: 1fr; }
        .panel { border: round $accent; padding: 1; height: auto; }
        #events { height: 1fr; }
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

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Vertical(id="body"):
                yield Static(_header_text(self.snapshot), id="header_panel", classes="panel")
                with Horizontal():
                    yield Static(
                        _coverage_text(self.snapshot), id="coverage_panel", classes="panel"
                    )
                    yield Static(
                        _findings_text(self.snapshot), id="findings_panel", classes="panel"
                    )
                yield Static(_task_text(self.snapshot), id="task_panel", classes="panel")
                yield Static(_agent_text(self.snapshot), id="agent_panel", classes="panel")
                yield Static(_events_text(self.controller.events), id="events", classes="panel")
                yield Static("q stop after current step | r refresh | h help | Ctrl-C interrupt")
            yield Footer()

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
            self.query_one("#header_panel", Static).update(_header_text(self.snapshot))
            self.query_one("#coverage_panel", Static).update(_coverage_text(self.snapshot))
            self.query_one("#findings_panel", Static).update(_findings_text(self.snapshot))
            self.query_one("#task_panel", Static).update(_task_text(self.snapshot))
            self.query_one("#agent_panel", Static).update(_agent_text(self.snapshot))
            self.query_one("#events", Static).update(_events_text(self.controller.events))

    return RunApp(controller)


def _header_text(snapshot: RunSnapshot) -> str:
    return f"Review Gauntlet Run\nSession: {snapshot.session_id or 'none'}"


def _coverage_text(snapshot: RunSnapshot) -> str:
    return "Coverage\n" + _counts_text(snapshot.coverage)


def _findings_text(snapshot: RunSnapshot) -> str:
    return "Findings\n" + _counts_text(snapshot.findings)


def _task_text(snapshot: RunSnapshot) -> str:
    prompt = snapshot.next_ready_prompt or "No ready task"
    return f"Current task\n{prompt}"


def _agent_text(snapshot: RunSnapshot) -> str:
    argv = " ".join(snapshot.command_argv) if snapshot.command_argv else "n/a"
    return (
        "Agent\n"
        f"status={snapshot.agent_status} step={snapshot.step} "
        f"elapsed={snapshot.elapsed_seconds:.1f}s\nargv={argv}"
    )


def _events_text(events: tuple[RunEvent, ...]) -> str:
    lines = ["Events"]
    for event in events[-12:]:
        payload = " ".join(f"{key}={value}" for key, value in event.payload.items())
        lines.append(f"{event.timestamp} {event.type} {payload}".rstrip())
    return "\n".join(lines)


def _counts_text(counts: dict[str, object]) -> str:
    if not counts:
        return "-"
    return "\n".join(f"{key}: {value}" for key, value in sorted(counts.items()))
