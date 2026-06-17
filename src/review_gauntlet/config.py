from __future__ import annotations

import copy
import json
import math
import os
import re
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TEMPLATE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

CONFIG_DISCOVERY_NAMES = (
    ".review-gauntlet/config.jsonc",
    ".review-gauntlet/config.json",
    "review-gauntlet.jsonc",
    "review-gauntlet.json",
)
PROJECT_CONFIG_PATH = Path(".review-gauntlet/config.jsonc")
GLOBAL_CONFIG_PATH = Path("review-gauntlet/config.jsonc")
XDG_CONFIG_DISCOVERY_NAMES = (
    "config.jsonc",
    "config.json",
)
PRESET_NAMES = ("claude", "opencode", "codex")
BUILTIN_DEFAULT_CONFIG: dict[str, Any] = {}
SUPPORTED_TEMPLATE_VARIABLES = frozenset(
    {
        "repo_root",
        "state_dir",
        "run_id",
        "run_dir",
        "cell_id",
        "cell_dir",
        "prompt",
        "output_file",
        "file_path",
        "rule_id",
    }
)
HOOK_TEMPLATE_VARIABLES = frozenset(
    {
        "event_type",
        "timestamp",
        "repo_root",
        "state_dir",
        "session_id",
        "step",
        "reason",
        "returncode",
    }
)
SUPPORTED_HOOK_EVENTS = frozenset(
    {
        "run_started",
        "step_started",
        "agent_started",
        "agent_finished",
        "failed",
        "blocked",
        "checkpoint_commit_started",
        "checkpoint_commit_finished",
        "finalized",
        "stop_requested",
        "interrupt_requested",
        "interrupted",
    }
)
DEFAULT_HOOK_TIMEOUT_SECONDS = 30.0


class ConfigError(ValueError):
    pass


class OutputMode(StrEnum):
    STDOUT_JSON = "stdout-json"
    FILE_JSON = "file-json"


class CommandOutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: OutputMode = OutputMode.FILE_JSON
    path: str | None = None

    @model_validator(mode="after")
    def validate_path_for_file_output(self) -> CommandOutputConfig:
        if self.mode == OutputMode.STDOUT_JSON and self.path is not None:
            raise ValueError("adapter.output.path is only supported for file-json output")
        return self


class HookCommandConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str
    args: tuple[str, ...] = ()
    timeout_seconds: float = DEFAULT_HOOK_TIMEOUT_SECONDS
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("hook.command must be a non-empty executable name or path")
        if any(char.isspace() for char in value):
            raise ValueError("hook.command must be a single argv element, not a shell string")
        _validate_hook_template_string(value)
        return value

    @field_validator("args")
    @classmethod
    def validate_args(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _validate_hook_template_string(item)
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("hook.timeout_seconds must be a finite value greater than zero")
        return value

    @field_validator("cwd")
    @classmethod
    def validate_cwd(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_hook_template_string(value)
        return value

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if not ENV_NAME_PATTERN.fullmatch(key):
                raise ValueError(
                    "hook.env keys must be portable environment variable names "
                    "matching [A-Za-z_][A-Za-z0-9_]*"
                )
            _validate_hook_template_string(item)
        return value


class CommandAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["command"]
    command: str
    args: tuple[str, ...] = ()
    output: CommandOutputConfig = Field(default_factory=CommandOutputConfig)
    timeout_seconds: float = 3600.0
    quiet_timeout_seconds: float = 600.0
    verdict_grace_seconds: float = 30.0
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("adapter.command must be a non-empty executable name or path")
        if any(char.isspace() for char in value):
            raise ValueError("adapter.command must be a single argv element, not a shell string")
        _validate_template_string(value)
        return value

    @field_validator("args")
    @classmethod
    def validate_args(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _validate_template_string(item)
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("adapter.timeout_seconds must be a finite value greater than zero")
        return value

    @field_validator("quiet_timeout_seconds")
    @classmethod
    def validate_quiet_timeout(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(
                "adapter.quiet_timeout_seconds must be a finite value greater than zero"
            )
        return value

    @field_validator("verdict_grace_seconds")
    @classmethod
    def validate_verdict_grace(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(
                "adapter.verdict_grace_seconds must be a finite value greater than zero"
            )
        return value

    @field_validator("cwd")
    @classmethod
    def validate_cwd(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_template_string(value)
        return value

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if not ENV_NAME_PATTERN.fullmatch(key):
                raise ValueError(
                    "adapter.env keys must be portable environment variable names "
                    "matching [A-Za-z_][A-Za-z0-9_]*"
                )
            _validate_template_string(item)
        return value

    @model_validator(mode="after")
    def validate_output_templates(self) -> CommandAdapterConfig:
        if self.output.path is not None:
            _validate_template_string(self.output.path)
            _reject_template_variable(
                self.output.path,
                "prompt",
                "adapter.output.path must not use {prompt}; use {output_file}, {cell_dir}, "
                "or a deterministic path instead",
            )
        return self


class ReviewGauntletConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: CommandAdapterConfig
    hooks: dict[str, tuple[HookCommandConfig, ...]] = Field(default_factory=dict)

    @field_validator("hooks")
    @classmethod
    def validate_hooks(
        cls, value: dict[str, tuple[HookCommandConfig, ...]]
    ) -> dict[str, tuple[HookCommandConfig, ...]]:
        unknown_events = sorted(set(value) - SUPPORTED_HOOK_EVENTS)
        if unknown_events:
            supported = ", ".join(sorted(SUPPORTED_HOOK_EVENTS))
            unknown = ", ".join(unknown_events)
            raise ValueError(f"unsupported hook event(s): {unknown}; supported events: {supported}")
        return value


def discover_config_path(root: Path, explicit: Path | None = None) -> Path | None:
    repo_root = root.resolve()
    if explicit is not None:
        return resolve_explicit_config_path(repo_root, explicit)
    project_path = discover_project_config_path(repo_root)
    if project_path is not None:
        return project_path
    return discover_global_config_path()


def discover_project_config_path(root: Path) -> Path | None:
    repo_root = root.resolve()
    for name in CONFIG_DISCOVERY_NAMES:
        candidate = repo_root / name
        if candidate.is_file():
            return candidate
    return None


def discover_global_config_path() -> Path | None:
    xdg_config_dir = global_config_dir()
    for name in XDG_CONFIG_DISCOVERY_NAMES:
        candidate = xdg_config_dir / name
        if candidate.is_file():
            return candidate
    return None


def resolve_explicit_config_path(root: Path, explicit: Path) -> Path:
    repo_root = root.resolve()
    expanded = explicit.expanduser()
    resolved = expanded.resolve() if expanded.is_absolute() else (repo_root / expanded).resolve()
    if not resolved.exists():
        raise ConfigError(f"review config does not exist: {explicit}")
    if not resolved.is_file():
        raise ConfigError(f"review config is not a file: {explicit}")
    return resolved


def global_config_dir() -> Path:
    return _xdg_config_home() / "review-gauntlet"


def default_global_config_path() -> Path:
    return _xdg_config_home() / GLOBAL_CONFIG_PATH


def default_project_config_path(root: Path) -> Path:
    return root.resolve() / PROJECT_CONFIG_PATH


def _xdg_config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".config").resolve()


def load_config(
    root: Path, explicit: Path | None = None
) -> tuple[Path, ReviewGauntletConfig] | None:
    resolved = resolve_effective_config(root, explicit)
    if resolved is None or resolved.path is None:
        return None
    return resolved.path, resolved.config


class EffectiveConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path | None
    sources: tuple[Path, ...]
    config: ReviewGauntletConfig


def resolve_effective_config(root: Path, explicit: Path | None = None) -> EffectiveConfig | None:
    repo_root = root.resolve()
    sources: list[Path] = []
    merged: dict[str, Any] = copy.deepcopy(BUILTIN_DEFAULT_CONFIG)
    if explicit is None:
        global_path = discover_global_config_path()
        if global_path is not None:
            merged = deep_merge(merged, load_raw_config(global_path))
            sources.append(global_path)
        project_path = discover_project_config_path(repo_root)
        if project_path is not None:
            merged = deep_merge(merged, load_raw_config(project_path))
            sources.append(project_path)
    else:
        explicit_path = resolve_explicit_config_path(repo_root, explicit)
        merged = deep_merge(merged, load_raw_config(explicit_path))
        sources.append(explicit_path)
    if not merged:
        return None
    try:
        return EffectiveConfig(
            path=sources[-1] if sources else None,
            sources=tuple(sources),
            config=ReviewGauntletConfig.model_validate(merged),
        )
    except Exception as exc:
        source_text = ", ".join(str(source) for source in sources) or "built-in defaults"
        raise ConfigError(
            f"invalid review config from effective sources {source_text}: {exc}"
        ) from exc


def load_raw_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(_strip_jsonc(text))
    except Exception as exc:
        raise ConfigError(f"invalid review config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"invalid review config {path}: top-level value must be an object")
    return cast(dict[str, Any], raw)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = deep_merge(cast(dict[str, Any], existing), cast(dict[str, Any], value))
        else:
            result[key] = copy.deepcopy(value)
    return result


def list_presets() -> tuple[str, ...]:
    return PRESET_NAMES


def read_preset(name: str) -> str:
    if name not in PRESET_NAMES:
        raise ConfigError(f"unknown config preset: {name}")
    return (
        resources.files("review_gauntlet.presets")
        .joinpath(f"{name}.jsonc")
        .read_text(encoding="utf-8")
    )


def validate_config_text(text: str, *, source: str) -> ReviewGauntletConfig:
    try:
        raw = json.loads(_strip_jsonc(text))
        return ReviewGauntletConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigError(f"invalid review config {source}: {exc}") from exc


def _validate_template_string(value: str) -> None:
    _validate_template_string_with_variables(value, SUPPORTED_TEMPLATE_VARIABLES)


def _validate_hook_template_string(value: str) -> None:
    _validate_template_string_with_variables(value, HOOK_TEMPLATE_VARIABLES)


def _validate_template_string_with_variables(value: str, variables: frozenset[str]) -> None:
    literal_removed = value.replace("{{", "").replace("}}", "")
    for match in TEMPLATE_PATTERN.finditer(literal_removed):
        name = match.group(1)
        if name not in variables:
            raise ValueError(f"unsupported template variable {{{name}}}")
    brace_depth = 0
    index = 0
    while index < len(value):
        pair = value[index : index + 2]
        if pair in {"{{", "}}"}:
            index += 2
            continue
        if value[index] == "{":
            brace_depth += 1
        elif value[index] == "}":
            brace_depth -= 1
            if brace_depth < 0:
                break
        index += 1
    if brace_depth != 0:
        raise ValueError(
            "unsupported template literal brace; literal braces must be balanced or escaped "
            "as '{{' and '}}'"
        )


def _reject_template_variable(value: str, variable: str, message: str) -> None:
    literal_removed = value.replace("{{", "").replace("}}", "")
    if any(match.group(1) == variable for match in TEMPLATE_PATTERN.finditer(literal_removed)):
        raise ValueError(message)


def _strip_jsonc(text: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            if index + 1 >= len(text):
                raise ConfigError("unterminated JSONC block comment")
            index += 2
            continue
        result.append(char)
        index += 1
    return _remove_trailing_commas("".join(result))


def _remove_trailing_commas(text: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "}]":
                index += 1
                continue
        result.append(char)
        index += 1
    return "".join(result)
