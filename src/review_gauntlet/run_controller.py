from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from review_gauntlet.config import CommandAdapterConfig, load_config
from review_gauntlet.session_store import SessionStore

RUN_INTERRUPTED_ERROR = "run interrupted by user"
RUN_INTERRUPTED_REASON = "interrupted"


@dataclass(frozen=True)
class SessionCommandResult:
    argv: list[str]
    cwd: str | None
    returncode: int | None
    stdout: str
    stderr: str
    failure: dict[str, object] | None = None


@dataclass(frozen=True)
class RunEvent:
    type: str
    timestamp: str
    payload: dict[str, object]

    @classmethod
    def create(cls, event_type: str, **payload: object) -> RunEvent:
        return cls(
            type=event_type,
            timestamp=datetime.now(UTC).isoformat(),
            payload=dict(payload),
        )

    def model_dump(self) -> dict[str, object]:
        return {"type": self.type, "timestamp": self.timestamp, **self.payload}


@dataclass(frozen=True)
class RunSnapshot:
    session_id: str | None
    coverage: dict[str, object]
    findings: dict[str, object]
    next_ready_prompt: str | None
    step: int
    agent_status: str
    command_argv: tuple[str, ...]
    elapsed_seconds: float


ReadyPrompt = Callable[[SessionStore, Path], str | None]
StatusSnapshot = Callable[[SessionStore, Path], dict[str, object]]
CommandRunner = Callable[[CommandAdapterConfig, Path, Path, str], SessionCommandResult]
EventSink = Callable[[RunEvent], None]


class RunController:
    def __init__(
        self,
        *,
        root: Path,
        store: SessionStore,
        config_path: Path | None,
        max_steps: int,
        ready_prompt: ReadyPrompt,
        status_snapshot: StatusSnapshot,
        command_runner: CommandRunner,
        event_sink: EventSink | None = None,
    ) -> None:
        self.root = root
        self.store = store
        self.config_path = config_path
        self.max_steps = max_steps
        self._ready_prompt = ready_prompt
        self._status_snapshot = status_snapshot
        self._command_runner = command_runner
        self._event_sink = event_sink
        self._events: list[RunEvent] = []
        self._stop_after_current_step = False
        self._interrupted = False
        self._step = 0
        self._agent_status = "idle"
        self._command_argv: tuple[str, ...] = ()
        self._started_at = datetime.now(UTC)

    @property
    def events(self) -> tuple[RunEvent, ...]:
        return tuple(self._events)

    def request_stop_after_current_step(self) -> None:
        self._stop_after_current_step = True
        self._emit("stop_requested", mode="after_current_step")

    def interrupt(self) -> None:
        self._interrupted = True
        self._emit("interrupt_requested")

    def refresh(self) -> RunSnapshot:
        snapshot = self.snapshot()
        self._emit("status_refreshed", session_id=snapshot.session_id)
        return snapshot

    def snapshot(self) -> RunSnapshot:
        status: dict[str, object]
        try:
            session_id = self.store.active_session_id()
            status = self._status_snapshot(self.store, self.root)
            ready = self._ready_prompt(self.store, self.root)
        except LookupError:
            session_id = None
            status = {"coverage": {}, "findings": {}}
            ready = None
        return RunSnapshot(
            session_id=session_id,
            coverage=_object_dict(status.get("coverage", {})),
            findings=_object_dict(status.get("findings", {})),
            next_ready_prompt=ready,
            step=self._step,
            agent_status=self._agent_status,
            command_argv=self._command_argv,
            elapsed_seconds=(datetime.now(UTC) - self._started_at).total_seconds(),
        )

    def run(self) -> dict[str, object]:
        loaded = load_config(self.root, self.config_path)
        if loaded is None:
            raise ValueError(
                "run requires a command adapter config. Create one with "
                "`review-gauntlet config init --preset opencode`, create a global default with "
                "`review-gauntlet config init --global --preset opencode`, or inspect presets with "
                "`review-gauntlet config preset list`."
            )
        _config_path, effective_config = loaded
        steps: list[dict[str, object]] = []
        initial_session_id = self._active_session_id_or_none()
        self._emit("run_started", session_id=initial_session_id, max_steps=self.max_steps)
        self.refresh()
        for step_number in range(1, self.max_steps + 1):
            self._step = step_number
            if self._interrupted:
                return self._interrupted_result(
                    steps, error="run interrupted by controller request"
                )
            session_id = self.store.active_session_id()
            prompt = self._ready_prompt(self.store, self.root)
            if prompt is None:
                self._emit("blocked", reason="no_ready_task", session_id=session_id)
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason="no_ready_task",
                    error="active session remains but no ready task is actionable",
                    session_id=session_id,
                )
            self._emit("step_started", step=step_number, prompt=prompt)
            self._agent_status = "running"
            self._emit("agent_started", argv=[], step=step_number)
            try:
                command_result = self._command_runner(
                    effective_config.adapter,
                    self.root,
                    self.store.state_dir,
                    prompt,
                )
            except KeyboardInterrupt:
                self._agent_status = "interrupted"
                self._emit("interrupted", step=step_number, session_id=session_id)
                return self._interrupted_result(steps)
            self._command_argv = tuple(command_result.argv)
            step_payload = _run_step_payload(step_number, prompt, command_result)
            steps.append(step_payload)
            self._agent_status = "idle"
            self._emit(
                "agent_finished",
                returncode=command_result.returncode,
                step=step_number,
                failed=command_result.failure is not None,
            )
            if command_result.failure is not None:
                self._emit("failed", reason=command_result.failure.get("reason", "command_failed"))
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason=str(command_result.failure.get("reason", "command_failed")),
                    error=str(command_result.failure.get("error", "command failed")),
                    session_id=session_id,
                )
            if not self.store.active_path.exists():
                self._emit("finalized", session_id=session_id)
                return _run_result(
                    completed=True,
                    steps=steps,
                    reason="completed",
                    error=None,
                    session_id=session_id,
                )
            if self._stop_after_current_step:
                self._emit("blocked", reason="stop_after_current_step", session_id=session_id)
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason="stop_after_current_step",
                    error="active session remains after stop-after-current-step request",
                    session_id=session_id,
                )
            self.refresh()
        session_id = self._active_session_id_or_none()
        if session_id is None:
            self._emit("finalized", session_id=None)
            return _run_result(
                completed=True,
                steps=steps,
                reason="completed",
                error=None,
                session_id=None,
            )
        self._emit("failed", reason="max_steps_exhausted", session_id=session_id)
        return _run_result(
            completed=False,
            steps=steps,
            reason="max_steps_exhausted",
            error=f"active session remains after {self.max_steps} run step(s)",
            session_id=session_id,
            max_steps=self.max_steps,
        )

    def _emit(self, event_type: str, **payload: object) -> None:
        event = RunEvent.create(event_type, **payload)
        self._events.append(event)
        if self._event_sink is not None:
            self._event_sink(event)

    def _interrupted_result(
        self, steps: list[dict[str, object]], *, error: str = RUN_INTERRUPTED_ERROR
    ) -> dict[str, object]:
        return _run_result(
            completed=False,
            steps=steps,
            reason=RUN_INTERRUPTED_REASON,
            error=error,
            session_id=self._active_session_id_or_none(),
        )

    def _active_session_id_or_none(self) -> str | None:
        try:
            return self.store.active_session_id()
        except LookupError:
            return None


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    typed_value = cast(Mapping[object, object], value)
    return {str(key): item for key, item in typed_value.items()}


def _run_result(
    *,
    completed: bool,
    steps: list[dict[str, object]],
    reason: str,
    error: str | None,
    session_id: str | None,
    max_steps: int | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "completed": completed,
        "reason": reason,
        "steps": steps,
        "step_count": len(steps),
        "session_id": session_id,
    }
    if error is not None:
        result["error"] = error
    if max_steps is not None:
        result["max_steps"] = max_steps
    return result


def _run_step_payload(
    step_number: int, prompt: str, result: SessionCommandResult
) -> dict[str, object]:
    payload: dict[str, object] = {
        "step": step_number,
        "prompt": prompt,
        "argv": result.argv,
        "cwd": result.cwd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if result.failure is not None:
        payload["failure"] = result.failure
    return payload
