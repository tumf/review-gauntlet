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
from review_gauntlet.coverage_projection import CoverageProjection, empty_coverage_projection
from review_gauntlet.session_store import SessionStore
from review_gauntlet.subprocess_failures import subprocess_startup_failure_blocker

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
    verdict_metadata: dict[str, object] | None = None


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
    cell_terminal_count: int = 0
    agent_lifecycle: AgentLifecycle = AgentLifecycle()
    coverage_projection: CoverageProjection = empty_coverage_projection()


@dataclass(frozen=True)
class ReadyTask:
    prompt: str
    next_required_action: str


ReadyPrompt = Callable[[SessionStore, Path], ReadyTask | None]
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
class ProgressTarget:
    finding_ids: tuple[str, ...] = ()
    cell_ids: tuple[str, ...] = ()
    task_key: str | None = None

    @property
    def target_ids(self) -> tuple[str, ...]:
        return (*self.finding_ids, *self.cell_ids)


@dataclass(frozen=True)
class RunExecutionContext:
    agent_root: Path
    state_dir: Path

    @classmethod
    def from_active_session(
        cls, *, root: Path, store: SessionStore, session_id: str
    ) -> RunExecutionContext:
        store.session_metadata(session_id)  # raises LookupError if session missing
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
        self.cancel_event = threading.Event()
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
        self.cancel_event.set()
        self._emit("interrupt_requested")

    def refresh(self) -> RunSnapshot:
        snapshot = self.snapshot()
        self._emit("status_refreshed", session_id=snapshot.session_id)
        return snapshot

    def snapshot(self) -> RunSnapshot:
        status: dict[str, object]
        try:
            session_id = self.store.active_session_id()
        except LookupError:
            session_id = None
            status = {"coverage": {}, "findings": {}}
            ready = None
        else:
            try:
                status = self._status_snapshot(self.store, self.root)
            except Exception as exc:
                status = _status_unavailable_snapshot(exc)
                ready = None
            else:
                if "_next_ready_prompt" in status:
                    ready = _string_or_none(status.get("_next_ready_prompt"))
                else:
                    try:
                        ready_task = self._ready_prompt(self.store, self.root)
                    except LookupError:
                        session_id = None
                        status = {"coverage": {}, "findings": {}}
                        ready = None
                    except Exception as exc:
                        ready = None
                        status = _with_finalize_blocker(status, _readiness_unavailable_blocker(exc))
                    else:
                        ready = ready_task.prompt if ready_task is not None else None
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
            cell_terminal_count=_int_or_zero(status.get("cell_terminal_count", 0)),
            agent_lifecycle=self._current_agent_lifecycle(),
            coverage_projection=_coverage_projection_or_empty(status.get("coverage_projection")),
        )

    def _current_agent_lifecycle(self) -> AgentLifecycle:
        if self._agent_status != "running":
            return self._agent_lifecycle
        now = datetime.now(UTC)
        # Snapshot mutable fields to avoid TOCTOU races with run() thread
        lifecycle = self._agent_lifecycle
        step_started_at = self._agent_step_started_at
        timeout_seconds = self._agent_timeout_seconds
        output_progress = self._agent_output_progress
        last_output_age = lifecycle.last_output_age_seconds
        output_tail = lifecycle.output_tail
        if output_progress is not None:
            progress_age, progress_tail = output_progress.snapshot()
            if progress_tail:
                last_output_age = progress_age
                output_tail = progress_tail
        if last_output_age is None and step_started_at is not None:
            last_output_age = (now - step_started_at).total_seconds()
        timeout_remaining = lifecycle.timeout_remaining_seconds
        if timeout_remaining is None and timeout_seconds is not None:
            elapsed = (
                (now - step_started_at).total_seconds() if step_started_at is not None else 0.0
            )
            timeout_remaining = max(0.0, float(timeout_seconds) - elapsed)
        status = lifecycle.status
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
            timeout_seconds=timeout_seconds,
            artifact_path=lifecycle.artifact_path,
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
            self.cancel_event.clear()
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
                ready_task = self._ready_prompt(self.store, self.root)
            except LookupError:
                self._emit("blocked", reason="session_disappeared")
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason="session_disappeared",
                    error="active session disappeared during run",
                    session_id=session_id,
                )
            if ready_task is None:
                self._emit("blocked", reason="no_ready_task", session_id=session_id)
                return _run_result(
                    completed=False,
                    steps=steps,
                    reason="no_ready_task",
                    error="active session remains but no ready task is actionable",
                    session_id=session_id,
                )
            prompt = ready_task.prompt
            next_required_action = ready_task.next_required_action
            progress_target = _progress_target_from_prompt(prompt)
            pre_turn_state = _target_state_snapshot(self.store, session_id, progress_target)
            self._emit(
                "step_started",
                step=step_number,
                prompt=prompt,
                next_required_action=next_required_action,
            )
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
            if _is_successful_progress_verdict(command_result):
                post_turn_state = _target_state_snapshot(self.store, session_id, progress_target)
                if pre_turn_state == post_turn_state:
                    metadata = command_result.verdict_metadata or {}
                    command_result = dataclasses.replace(
                        command_result,
                        failure={
                            "reason": "no_progress",
                            "error": "step verdict reported progress but no targeted state changed",
                            "task_key": str(
                                metadata.get("task_key", progress_target.task_key or "")
                            ),
                            "target_ids": list(progress_target.target_ids),
                        },
                    )
                    lifecycle_status = _lifecycle_status_from_result(command_result)
                    self._agent_lifecycle = dataclasses.replace(
                        self._agent_lifecycle,
                        status=lifecycle_status,
                    )
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


def _is_successful_progress_verdict(result: SessionCommandResult) -> bool:
    if result.failure is not None or result.verdict_metadata is None:
        return False
    return result.verdict_metadata.get("verdict") in {"continue", "finish"}


def _progress_target_from_prompt(prompt: str) -> ProgressTarget:
    finding_ids: list[str] = []
    cell_ids: list[str] = []
    task_key: str | None = None
    lines = prompt.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if "finding_id:" in stripped:
            finding_id = _value_after_label(stripped, "finding_id:")
            if finding_id and finding_id not in finding_ids:
                finding_ids.append(finding_id)
        if "cell_id:" in stripped:
            cell_id = _value_after_label(stripped, "cell_id:")
            if cell_id and cell_id not in cell_ids:
                cell_ids.append(cell_id)
        if (
            stripped == "Before ending this turn, write valid JSON to the following path:"
            and index + 1 < len(lines)
        ):
            task_key = Path(lines[index + 1].strip()).name
    if finding_ids:
        cell_ids = []
    return ProgressTarget(tuple(finding_ids), tuple(cell_ids), task_key)


def _value_after_label(line: str, label: str) -> str | None:
    try:
        remainder = line.split(label, 1)[1]
    except IndexError:
        return None
    value = remainder.split(";", 1)[0].strip()
    return value or None


def _target_state_snapshot(
    store: SessionStore, session_id: str, target: ProgressTarget
) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if target.cell_ids:
        cell_ids = set(target.cell_ids)
        for row in store.list_cells(session_id):
            cell_id = str(row["cell_id"])
            if cell_id in cell_ids:
                snapshot[f"cell:{cell_id}"] = str(row["state"])
    if target.finding_ids:
        finding_ids = set(target.finding_ids)
        with store.connect() as conn:
            rows = conn.execute(
                "select finding_id, state from findings where session_id = ?",
                (session_id,),
            ).fetchall()
        for row in rows:
            finding_id = str(row["finding_id"])
            if finding_id in finding_ids:
                snapshot[f"finding:{finding_id}"] = str(row["state"])
    return snapshot


def _status_unavailable_snapshot(error: Exception) -> dict[str, object]:
    return {
        "coverage": {},
        "findings": {},
        "can_finalize": False,
        "finalize_blockers": (_snapshot_unavailable_blocker("status snapshot", error),),
        "next_required_action": "resolve_finalize_blockers",
    }


def _readiness_unavailable_blocker(error: Exception) -> str:
    return _snapshot_unavailable_blocker("ready prompt", error)


def _snapshot_unavailable_blocker(operation: str, error: Exception) -> str:
    if isinstance(error, OSError):
        return subprocess_startup_failure_blocker("git status checks", ("git", "status"), error)
    return (
        f"{operation} unavailable: {error.__class__.__name__}: {error}; "
        "next_action=retry_after_resolving_runtime_error"
    )


def _with_finalize_blocker(status: dict[str, object], blocker: str) -> dict[str, object]:
    blockers = [*_string_tuple(status.get("finalize_blockers", ())), blocker]
    return {
        **status,
        "can_finalize": False,
        "finalize_blockers": tuple(dict.fromkeys(blockers)),
        "next_required_action": "resolve_finalize_blockers",
    }


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


def _coverage_projection_or_empty(value: object) -> CoverageProjection:
    if isinstance(value, CoverageProjection):
        return value
    return empty_coverage_projection()


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
    if reason in {"timeout", "quiet_timeout"}:
        return "timed_out"
    verdict_statuses = {
        "step_verdict_error": "verdict_error",
        "invalid_step_verdict": "verdict_invalid",
        "missing_step_verdict": "verdict_missing",
        "no_progress": "no_progress",
    }
    if reason in verdict_statuses:
        return verdict_statuses[reason]
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
    if result.verdict_metadata is not None:
        payload["verdict_metadata"] = result.verdict_metadata
    if result.failure is not None:
        payload["failure"] = result.failure
    return payload
