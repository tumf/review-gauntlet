from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from review_gauntlet.config import HOOK_TEMPLATE_VARIABLES, TEMPLATE_PATTERN, HookCommandConfig
from review_gauntlet.run_controller import EventSink, RunEvent

HOOK_EVENT_JSON_ENV = "REVIEW_GAUNTLET_EVENT_JSON"
HOOK_EVENT_TYPE_ENV = "REVIEW_GAUNTLET_EVENT_TYPE"
HOOK_REPO_ROOT_ENV = "REVIEW_GAUNTLET_REPO_ROOT"
HOOK_STATE_DIR_ENV = "REVIEW_GAUNTLET_STATE_DIR"


@dataclass(frozen=True)
class HookExecutionResult:
    argv: list[str]
    cwd: str | None
    event_type: str
    hook_index: int
    returncode: int | None
    stdout_artifact: str
    stderr_artifact: str
    result_artifact: str
    timed_out: bool = False
    failure_reason: str | None = None
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.failure_reason is not None or self.returncode not in (0, None)


def create_hook_event_sink(
    *, hooks: dict[str, tuple[HookCommandConfig, ...]], root: Path, state_dir: Path
) -> EventSink:
    dispatcher = HookDispatcher(hooks=hooks, root=root, state_dir=state_dir)
    return dispatcher.handle_event


class HookDispatcher:
    def __init__(
        self, *, hooks: dict[str, tuple[HookCommandConfig, ...]], root: Path, state_dir: Path
    ) -> None:
        self._hooks = hooks
        self._root = root.resolve()
        self._state_dir = state_dir.resolve()

    def handle_event(self, event: RunEvent) -> None:
        configured_hooks = self._hooks.get(event.type, ())
        if not configured_hooks:
            return
        context = _hook_template_context(event, root=self._root, state_dir=self._state_dir)
        event_json = json.dumps(event.model_dump(), sort_keys=True)
        for index, hook in enumerate(configured_hooks, start=1):
            result = self._execute_hook(hook, event, context, event_json, index)
            if result.failure_reason is not None or result.returncode not in (0, None):
                reason = result.failure_reason or f"exit_{result.returncode}"
                print(
                    "review-gauntlet hook warning: "
                    f"event={event.type} index={index} reason={reason} "
                    f"artifact={result.result_artifact}",
                    file=sys.stderr,
                )

    def _execute_hook(
        self,
        hook: HookCommandConfig,
        event: RunEvent,
        context: dict[str, str],
        event_json: str,
        hook_index: int,
    ) -> HookExecutionResult:
        artifact_dir = self._artifact_dir(event.type)
        stdout_path = artifact_dir / "stdout.log"
        stderr_path = artifact_dir / "stderr.log"
        result_path = artifact_dir / "result.json"
        argv: list[str] = []
        cwd_text: str | None = None
        stdout = ""
        stderr = ""
        returncode: int | None = None
        timed_out = False
        failure_reason: str | None = None
        error: str | None = None
        try:
            argv = [_expand_hook_template(hook.command, context)]
            argv.extend(_expand_hook_template(arg, context) for arg in hook.args)
            cwd_path = _resolve_hook_cwd(hook.cwd, self._root, context)
            cwd_text = str(cwd_path)
            env = os.environ.copy()
            env.update(_default_hook_env(event_json, context))
            env.update(
                {key: _expand_hook_template(value, context) for key, value in hook.env.items()}
            )
            completed = subprocess.run(
                argv,
                cwd=cwd_path,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                shell=False,
                timeout=hook.timeout_seconds,
                check=False,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            returncode = completed.returncode
            if completed.returncode != 0:
                failure_reason = "command_failed"
                error = f"hook command exited with status {completed.returncode}"
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            failure_reason = "timeout"
            error = f"hook command timed out after {hook.timeout_seconds} seconds"
            stdout = _output_to_text(exc.stdout)
            stderr = _output_to_text(exc.stderr)
        except FileNotFoundError as exc:
            failure_reason = "startup_error"
            error = f"hook command not found: {argv[0] if argv else hook.command}"
            stderr = str(exc)
        except ValueError as exc:
            failure_reason = "template_error"
            error = str(exc)
            stderr = str(exc)
        except OSError as exc:
            failure_reason = "startup_error"
            error = str(exc)
            stderr = str(exc)
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        result = HookExecutionResult(
            argv=argv,
            cwd=cwd_text,
            event_type=event.type,
            hook_index=hook_index,
            returncode=returncode,
            stdout_artifact=str(stdout_path),
            stderr_artifact=str(stderr_path),
            result_artifact=str(result_path),
            timed_out=timed_out,
            failure_reason=failure_reason,
            error=error,
        )
        result_path.write_text(
            json.dumps(
                {
                    "argv": result.argv,
                    "cwd": result.cwd,
                    "event_type": result.event_type,
                    "event_timestamp": event.timestamp,
                    "hook_index": result.hook_index,
                    "returncode": result.returncode,
                    "timed_out": result.timed_out,
                    "failure_reason": result.failure_reason,
                    "error": result.error,
                    "stdout_artifact": result.stdout_artifact,
                    "stderr_artifact": result.stderr_artifact,
                    "result_artifact": result.result_artifact,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return result

    def _artifact_dir(self, event_type: str) -> Path:
        safe_event_type = re.sub(r"[^A-Za-z0-9_.-]+", "_", event_type)
        artifact_dir = self._state_dir / "runs" / "hooks" / safe_event_type / uuid.uuid4().hex
        artifact_dir.mkdir(parents=True, exist_ok=False)
        return artifact_dir


def _hook_template_context(event: RunEvent, *, root: Path, state_dir: Path) -> dict[str, str]:
    payload = event.payload
    return {
        "event_type": event.type,
        "timestamp": event.timestamp,
        "repo_root": str(root.resolve()),
        "state_dir": str(state_dir.resolve()),
        "session_id": _payload_text(payload.get("session_id")),
        "step": _payload_text(payload.get("step")),
        "reason": _payload_text(payload.get("reason")),
        "returncode": _payload_text(payload.get("returncode")),
    }


def _payload_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "")


def _expand_hook_template(value: str, variables: dict[str, str]) -> str:
    placeholder = "\x00REVIEW_GAUNTLET_LITERAL_BRACE\x00"
    protected = value.replace("{{", placeholder + "OPEN").replace("}}", placeholder + "CLOSE")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in HOOK_TEMPLATE_VARIABLES:
            raise ValueError(
                f"template variable {{{name}}} is not available for hooks; supported variables: "
                + ", ".join(f"{{{item}}}" for item in sorted(HOOK_TEMPLATE_VARIABLES))
            )
        return variables.get(name, "").replace("\x00", "")

    expanded = TEMPLATE_PATTERN.sub(replace, protected)
    return expanded.replace(placeholder + "OPEN", "{").replace(placeholder + "CLOSE", "}")


def _resolve_hook_cwd(cwd: str | None, root: Path, variables: dict[str, str]) -> Path:
    root = root.resolve()
    if cwd is None:
        return root
    expanded = Path(_expand_hook_template(cwd, variables))
    resolved = (root / expanded).resolve() if not expanded.is_absolute() else expanded.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"hook.cwd must stay inside repository root: {resolved}") from exc
    if not resolved.is_dir():
        raise ValueError(f"hook.cwd is not a directory: {resolved}")
    return resolved


def _default_hook_env(event_json: str, context: dict[str, str]) -> dict[str, str]:
    return {
        HOOK_EVENT_JSON_ENV: event_json,
        HOOK_EVENT_TYPE_ENV: context["event_type"],
        HOOK_REPO_ROOT_ENV: context["repo_root"],
        HOOK_STATE_DIR_ENV: context["state_dir"],
        "REVIEW_GAUNTLET_EVENT_TIMESTAMP": context["timestamp"],
        "REVIEW_GAUNTLET_SESSION_ID": context["session_id"],
        "REVIEW_GAUNTLET_STEP": context["step"],
        "REVIEW_GAUNTLET_REASON": context["reason"],
        "REVIEW_GAUNTLET_RETURNCODE": context["returncode"],
    }


def _output_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)
