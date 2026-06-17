from __future__ import annotations

import dataclasses
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from review_gauntlet.checkpoint import CheckpointCommitResult, commit_latest_checkpoint
from review_gauntlet.config import CommandAdapterConfig, load_config
from review_gauntlet.session_store import SessionStore

RUN_INTERRUPTED_ERROR = "run interrupted by user"
RUN_INTERRUPTED_REASON = "interrupted"
AGENT_QUIET_THRESHOLD_SECONDS = 5.0


@dataclass(frozen=True)
class AgentOutputEntry:
    stream: str
    text: str
    timestamp: str | None = None


class AgentOutputProgress:
    def __init__(self, *, limit: int = 20) -> None:
        self._limit = limit
        self._lock = threading.Lock()
        self._last_output_at: datetime | None = None
        self._output_lines: list[AgentOutputEntry] = []

    def push(self, stream: str, text: str) -> None:
        timestamp = datetime.now(UTC)
        entry = AgentOutputEntry(stream=stream, text=text, timestamp=timestamp.isoformat())
        with self._lock:
            self._last_output_at = timestamp
            self._output_lines.append(entry)
            if len(self._output_lines) > self._limit:
                del self._output_lines[: len(self._output_lines) - self._limit]

    def snapshot(self) -> tuple[float | None, tuple[AgentOutputEntry, ...]]:
        with self._lock:
            last_output_at = self._last_output_at
            output_tail = tuple(self._output_lines)
        if last_output_at is None:
            return None, output_tail
        now = datetime.now(UTC)
        return (now - last_output_at).total_seconds(), output_tail


@dataclass(frozen=True)
class AgentLifecycle:
    status: str = "idle"
    last_output_age_seconds: float | None = None
    timeout_remaining_seconds: float | None = None
    timeout_seconds: float | None = None
    artifact_path: str | None = None
    output_tail: tuple[AgentOutputEntry, ...] = ()


@dataclass(frozen=True)
class SessionCommandResult:
    argv: list[str]
    cwd: str | None
    returncode: int | None
    stdout: str
    stderr: str
    failure: dict[str, object] | None = None
    stdout_artifact: str | None = None
    stderr_artifact: str | None = None
    activity_artifact: str | None = None
    output_tail: tuple[AgentOutputEntry, ...] = ()


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

    _RESERVED_KEYS = frozenset({"type", "timestamp"})

    def model_dump(self) -> dict[str, object]:
        conflicts = self._RESERVED_KEYS & self.payload.keys()
        if conflicts:
            raise ValueError(f"RunEvent payload contains reserved key(s): {conflicts}")
        result = dict(self.payload)
        result["type"] = self.type
        result["timestamp"] = self.timestamp
        return result


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
    command_label: str | None = None
    session_state: str | None = None
    can_finalize: bool = False
    finalize_blockers: tuple[str, ...] = ()
    next_required_action: str | None = None
    run_count: int = 0
    agent_lifecycle: AgentLifecycle = AgentLifecycle()


ReadyPrompt = Callable[[SessionStore, Path], str | None]
StatusSnapshot = Callable[[SessionStore, Path], dict[str, object]]
CommandRunner = Callable[[CommandAdapterConfig, Path, Path, str], SessionCommandResult]
EventSink = Callable[[RunEvent], None]


def compose_event_sinks(*sinks: EventSink | None) -> EventSink | None:
    active_sinks = tuple(sink for sink in sinks if sink is not None)
    if not active_sinks:
        return None
    if len(active_sinks) == 1:
        return active_sinks[0]

    def emit_to_all(event: RunEvent) -> None:
        for sink in active_sinks:
            sink(event)

    return emit_to_all


@dataclass(frozen=True)
class RunExecutionContext:
    agent_root: Path
    state_dir: Path

    @classmethod
    def from_active_session(
        cls, *, root: Path, store: SessionStore, session_id: str
    ) -> RunExecutionContext:
        store.session_metadata(session_id)
        return cls(agent_root=root, state_dir=store.state_dir)


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
        if max_steps < 1:
            raise ValueError(f"max_steps must be a positive integer, got {max_steps}")
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
        self._command_label: str | None = None
        self._agent_lifecycle = AgentLifecycle()
        self._agent_step_started_at: datetime | None = None
        self._agent_timeout_seconds: float | None = None
        self._agent_output_progress: AgentOutputProgress | None = None
        self._started_at = datetime.now(UTC)

    def set_agent_step_started_at_for_testing(self, started_at: datetime) -> None:
        self._agent_step_started_at = started_at

    @property
    def events(self) -> tuple[RunEvent, ...]:
        return tuple(self._events)

    @property
    def agent_output_progress(self) -> AgentOutputProgress | None:
        return self._agent_output_progress

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
            findings=_object_dict(status.get("findings", status.get("finding_state_counts", {}))),
            next_ready_prompt=ready,
            step=self._step,
            agent_status=self._agent_status,
            command_argv=self._command_argv,
            elapsed_seconds=(datetime.now(UTC) - self._started_at).total_seconds(),
            command_label=self._command_label,
            session_state=_string_or_none(status.get("session_state")),
            can_finalize=bool(status.get("can_finalize", False)),
            finalize_blockers=_string_tuple(status.get("finalize_blockers", ())),
            next_required_action=_string_or_none(status.get("next_required_action")),
            run_count=_int_or_zero(status.get("run_count", self._step)),
            agent_lifecycle=self._current_agent_lifecycle(),
        )

    def _current_agent_lifecycle(self) -> AgentLifecycle:
        if self._agent_status != "running":
            return self._agent_lifecycle
        now = datetime.now(UTC)
        last_output_age = self._agent_lifecycle.last_output_age_seconds
        output_tail = self._agent_lifecycle.output_tail
        output_progress = self._agent_output_progress
        if output_progress is not None:
            progress_age, progress_tail = output_progress.snapshot()
            if progress_tail:
                last_output_age = progress_age
                output_tail = progress_tail
        if last_output_age is None and self._agent_step_started_at is not None:
            last_output_age = (now - self._agent_step_started_at).total_seconds()
        timeout_remaining = self._agent_lifecycle.timeout_remaining_seconds
        if timeout_remaining is None and self._agent_timeout_seconds is not None:
            elapsed = (
                (now - self._agent_step_started_at).total_seconds()
                if self._agent_step_started_at is not None
                else 0.0
            )
            timeout_remaining = max(0.0, float(self._agent_timeout_seconds) - elapsed)
        status = self._agent_lifecycle.status
        if (
            status == "running"
            and last_output_age is not None
            and last_output_age >= AGENT_QUIET_THRESHOLD_SECONDS
        ):
            status = "quiet"
        return AgentLifecycle(
            status=status,
            last_output_age_seconds=last_output_age,
            timeout_remaining_seconds=timeout_remaining,
            timeout_seconds=self._agent_timeout_seconds,
            artifact_path=self._agent_lifecycle.artifact_path,
            output_tail=output_tail,
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
        self._command_label = command_display_label(effective_config.adapter)
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
            session_id = self._active_session_id_or_none()
            if session_id is None:
                self._emit("blocked", reason="session_disappeared")
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason="session_disappeared",
                    error="active session disappeared during run",
                    session_id=None,
                )
            try:
                prompt = self._ready_prompt(self.store, self.root)
            except LookupError:
                self._emit("blocked", reason="session_disappeared")
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason="session_disappeared",
                    error="active session disappeared during run",
                    session_id=session_id,
                )
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
            self._agent_step_started_at = datetime.now(UTC)
            self._agent_timeout_seconds = effective_config.adapter.timeout_seconds
            self._agent_lifecycle = AgentLifecycle(
                status="running",
                timeout_seconds=effective_config.adapter.timeout_seconds,
            )
            self._agent_output_progress = AgentOutputProgress()
            self._emit(
                "agent_started",
                command_label=self._command_label,
                step=step_number,
            )
            execution_context = RunExecutionContext.from_active_session(
                root=self.root,
                store=self.store,
                session_id=session_id,
            )
            try:
                command_result = self._command_runner(
                    effective_config.adapter,
                    execution_context.agent_root,
                    execution_context.state_dir,
                    prompt,
                )
            except KeyboardInterrupt:
                self._agent_output_progress = None
                self._agent_status = RUN_INTERRUPTED_REASON
                self._agent_lifecycle = AgentLifecycle(
                    status=RUN_INTERRUPTED_REASON,
                    timeout_seconds=effective_config.adapter.timeout_seconds,
                )
                self._agent_step_started_at = None
                self._agent_timeout_seconds = None
                self._emit("interrupted", step=step_number, session_id=session_id)
                return self._interrupted_result(steps)
            self._agent_output_progress = None
            self._command_argv = tuple(command_result.argv)
            lifecycle_status = _lifecycle_status_from_result(command_result)
            self._agent_lifecycle = AgentLifecycle(
                status=lifecycle_status,
                last_output_age_seconds=0.0 if command_result.output_tail else None,
                timeout_seconds=effective_config.adapter.timeout_seconds,
                artifact_path=command_result.activity_artifact
                or command_result.stdout_artifact
                or command_result.stderr_artifact,
                output_tail=command_result.output_tail,
            )
            self._agent_step_started_at = None
            self._agent_timeout_seconds = None
            step_payload = _run_step_payload(step_number, prompt, command_result)
            steps.append(step_payload)
            if self._interrupted:
                self._agent_status = RUN_INTERRUPTED_REASON
                self._agent_lifecycle = AgentLifecycle(
                    status=RUN_INTERRUPTED_REASON,
                    timeout_seconds=effective_config.adapter.timeout_seconds,
                    artifact_path=command_result.activity_artifact
                    or command_result.stdout_artifact
                    or command_result.stderr_artifact,
                    output_tail=command_result.output_tail,
                )
                self._emit("interrupted", step=step_number, session_id=session_id)
                return self._interrupted_result(
                    steps, error="run interrupted by controller request"
                )
            self._agent_status = "idle" if command_result.failure is None else lifecycle_status
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
                checkpoint_commit = self._commit_finalized_checkpoint(session_id, command_result)
                self._emit(
                    "checkpoint_commit_finished",
                    session_id=session_id,
                    committed=checkpoint_commit.committed,
                    reason=checkpoint_commit.reason,
                    commit=checkpoint_commit.commit,
                )
                self._mark_finalized()
                self._emit("finalized", session_id=session_id)
                return _run_result(
                    completed=True,
                    steps=steps,
                    reason="completed",
                    error=None,
                    session_id=session_id,
                    checkpoint_commit=checkpoint_commit,
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
            self._mark_finalized()
            self._emit("finalized", session_id=None)
            return _run_result(
                completed=True,
                steps=steps,
                reason="completed",
                error=None,
                session_id=None,
            )
        self._agent_status = "max_steps_exhausted"
        self._agent_lifecycle = AgentLifecycle(status="max_steps_exhausted")
        self._emit("failed", reason="max_steps_exhausted", session_id=session_id)
        return _run_result(
            completed=False,
            steps=steps,
            reason="max_steps_exhausted",
            error=f"active session remains after {self.max_steps} run step(s)",
            session_id=session_id,
            max_steps=self.max_steps,
        )

    def _commit_finalized_checkpoint(
        self, session_id: str, command_result: SessionCommandResult
    ) -> CheckpointCommitResult:
        self._emit("checkpoint_commit_started", session_id=session_id)
        generated_files = checkpoint_generated_files_from_stdout(command_result.stdout)
        return commit_latest_checkpoint(
            self.root,
            session_id=session_id,
            generated_files=generated_files,
        )

    def _mark_finalized(self) -> None:
        self._agent_status = "finalized"
        self._agent_lifecycle = AgentLifecycle(status="finalized")
        self._agent_step_started_at = None
        self._agent_timeout_seconds = None
        self._agent_output_progress = None

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


def command_display_label(config: CommandAdapterConfig) -> str:
    parts = (config.command, *config.args)
    visible_parts = [part for part in parts if "{" not in part and "}" not in part]
    if not visible_parts:
        return config.command
    return " ".join(visible_parts)


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    typed_value = cast(Mapping[object, object], value)
    return {str(key): item for key, item in typed_value.items()}


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, tuple | list):
        return ()
    items = cast(tuple[object, ...] | list[object], value)
    return tuple(text for item in items if (text := str(item)))


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


def _lifecycle_status_from_result(result: SessionCommandResult) -> str:
    if result.failure is None:
        return "completed"
    reason = str(result.failure.get("reason", "failed"))
    return _agent_status_from_failure_reason(reason)


def _agent_status_from_failure_reason(reason: str) -> str:
    if reason == "timeout":
        return "timed_out"
    if reason in {
        "command_failed",
        "startup_error",
        "template_error",
        RUN_INTERRUPTED_REASON,
        "max_steps_exhausted",
    }:
        return reason
    return "failed"


def _run_result(
    *,
    completed: bool,
    steps: list[dict[str, object]],
    reason: str,
    error: str | None,
    session_id: str | None,
    max_steps: int | None = None,
    checkpoint_commit: CheckpointCommitResult | None = None,
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
    if checkpoint_commit is not None:
        result["checkpoint_commit"] = checkpoint_commit.model_dump()
    return result


def checkpoint_generated_files_from_stdout(stdout: str) -> tuple[str, ...]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    typed_payload = cast(dict[str, object], payload)
    raw_files = typed_payload.get("generated_files")
    if not isinstance(raw_files, list):
        verdict = typed_payload.get("verdict")
        if isinstance(verdict, dict):
            raw_files = cast(dict[str, object], verdict).get("generated_files")
    if not isinstance(raw_files, list):
        return ()
    typed_files = cast(list[object], raw_files)
    files: list[str] = []
    seen: set[str] = set()
    for item in typed_files:
        if not isinstance(item, str):
            continue
        if "\x00" in item:
            continue
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        normalized = relative.as_posix()
        if not normalized.startswith(".review-gauntlet/checkpoints/"):
            continue
        if relative.suffix != ".json":
            continue
        if normalized not in seen:
            files.append(normalized)
            seen.add(normalized)
    return tuple(files)


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
        "output_tail": [dataclasses.asdict(entry) for entry in result.output_tail],
    }
    if result.stdout_artifact is not None:
        payload["stdout_artifact"] = result.stdout_artifact
    if result.stderr_artifact is not None:
        payload["stderr_artifact"] = result.stderr_artifact
    if result.activity_artifact is not None:
        payload["activity_artifact"] = result.activity_artifact
    if result.failure is not None:
        payload["failure"] = result.failure
    return payload
