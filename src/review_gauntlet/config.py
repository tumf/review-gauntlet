from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TEMPLATE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

CONFIG_DISCOVERY_NAMES = (
    ".review-gauntlet/config.jsonc",
    ".review-gauntlet/config.json",
    "review-gauntlet.jsonc",
    "review-gauntlet.json",
)
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


class CommandAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["command"]
    command: str
    args: tuple[str, ...] = ()
    output: CommandOutputConfig = Field(default_factory=CommandOutputConfig)
    timeout_seconds: float = 600.0
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
        if value <= 0:
            raise ValueError("adapter.timeout_seconds must be greater than zero")
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
        return self


class ReviewGauntletConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: CommandAdapterConfig


def discover_config_path(root: Path, explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        if not explicit.is_file():
            raise ConfigError(f"review config does not exist: {explicit}")
        return explicit
    for name in CONFIG_DISCOVERY_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def load_config(
    root: Path, explicit: Path | None = None
) -> tuple[Path, ReviewGauntletConfig] | None:
    path = discover_config_path(root, explicit)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(_strip_jsonc(text))
        return path, ReviewGauntletConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigError(f"invalid review config {path}: {exc}") from exc


def _validate_template_string(value: str) -> None:
    literal_removed = value.replace("{{", "").replace("}}", "")
    for match in TEMPLATE_PATTERN.finditer(literal_removed):
        name = match.group(1)
        if name not in SUPPORTED_TEMPLATE_VARIABLES:
            raise ValueError(f"unsupported template variable {{{name}}}")
    if literal_removed.count("{") != literal_removed.count("}"):
        raise ValueError(
            "unsupported template literal brace; literal braces must be balanced or escaped "
            "as '{{' and '}}'"
        )


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
