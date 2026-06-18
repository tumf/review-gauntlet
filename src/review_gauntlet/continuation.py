from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from review_gauntlet.findings import FindingResolution

TASK_KEY_ACTION_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TASK_KEY_HASH_CHARS = 12


class ContinuationVerdictError(ValueError):
    """Raised when a run-turn continuation verdict is missing or invalid."""


class ContinuationVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    verdict: Literal["continue", "finish", "abort"]
    summary: str
    completed_finding_ids: tuple[str, ...] = Field(default_factory=tuple)
    remaining_finding_ids: tuple[str, ...] = Field(default_factory=tuple)
    resolutions: tuple[FindingResolution, ...] = Field(default_factory=tuple)
    next_turn_instructions: str | None = None
    error: str | None = None

    @field_validator("summary")
    @classmethod
    def validate_summary_non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must be a non-empty string")
        return text

    @field_validator("next_turn_instructions", mode="before")
    @classmethod
    def validate_next_turn_instructions(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            raise ValueError("next_turn_instructions must be a non-empty string when provided")
        if isinstance(value, str):
            return value.strip()
        raise ValueError("next_turn_instructions must be a string or null")

    @field_validator("completed_finding_ids", "remaining_finding_ids", mode="before")
    @classmethod
    def validate_id_list(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list | tuple):
            raise ValueError("must be a list of finding IDs")
        ids: list[str] = []
        seen: set[str] = set()
        typed_value = cast(tuple[object, ...] | list[object], value)
        for item in typed_value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("finding IDs must be non-empty strings")
            finding_id = item.strip()
            if finding_id not in seen:
                ids.append(finding_id)
                seen.add(finding_id)
        return tuple(ids)

    @model_validator(mode="after")
    def validate_error_contract(self) -> ContinuationVerdict:
        if self.verdict == "abort" and (self.error is None or not self.error.strip()):
            raise ValueError("abort verdicts require a non-empty error message")
        return self


def compute_task_key(reason: str, file_path: str) -> str:
    action = reason.strip()
    if not TASK_KEY_ACTION_PATTERN.fullmatch(action):
        raise ContinuationVerdictError(f"invalid continuation action for task key: {reason!r}")
    if not file_path or "\x00" in file_path:
        raise ContinuationVerdictError("continuation file_path must be a non-empty repository path")
    digest = hashlib.sha256(f"{action}\0{file_path}".encode()).hexdigest()[:TASK_KEY_HASH_CHARS]
    return f"{action}__{digest}.json"


def continuation_path_for_task(
    state_dir: Path, session_id: str, reason: str, file_path: str
) -> Path:
    task_key = compute_task_key(reason, file_path)
    path = state_dir / "turns" / session_id / task_key
    ensure_safe_continuation_path(path)
    return path


def ensure_safe_continuation_path(path: Path) -> None:
    parts = path.parts
    try:
        state_index = parts.index(".review-gauntlet")
    except ValueError as exc:
        raise ContinuationVerdictError(
            "continuation path must be under .review-gauntlet/turns/<session_id>/"
        ) from exc
    if len(parts) <= state_index + 3 or parts[state_index + 1] != "turns":
        raise ContinuationVerdictError(
            "continuation path must be under .review-gauntlet/turns/<session_id>/"
        )
    session_dir = Path(*parts[: state_index + 3])
    if path.name != compute_task_key_from_filename(path.name):
        raise ContinuationVerdictError(f"invalid continuation task key filename: {path.name}")
    try:
        path.resolve(strict=False).relative_to(session_dir.resolve(strict=False))
    except ValueError as exc:
        raise ContinuationVerdictError(
            f"continuation path escapes session turn directory: {path}"
        ) from exc


def compute_task_key_from_filename(filename: str) -> str:
    if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
        raise ContinuationVerdictError(f"invalid continuation task key filename: {filename!r}")
    if not filename.endswith(".json"):
        raise ContinuationVerdictError("continuation task key must end with .json")
    stem = filename.removesuffix(".json")
    action, separator, digest = stem.rpartition("__")
    if separator != "__" or not TASK_KEY_ACTION_PATTERN.fullmatch(action):
        raise ContinuationVerdictError(f"invalid continuation task key filename: {filename!r}")
    if len(digest) != TASK_KEY_HASH_CHARS or any(char not in "0123456789abcdef" for char in digest):
        raise ContinuationVerdictError(f"invalid continuation task key digest: {filename!r}")
    return filename


def validate_continuation_verdict(path: Path) -> ContinuationVerdict:
    ensure_safe_continuation_path(path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ContinuationVerdictError(f"continuation verdict file is missing: {path}") from exc
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ContinuationVerdictError(f"continuation verdict is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ContinuationVerdictError("continuation verdict JSON must be an object")
    try:
        verdict = ContinuationVerdict.model_validate(payload)
    except ValueError as exc:
        raise ContinuationVerdictError(f"invalid continuation verdict schema: {exc}") from exc
    return verdict


def continuation_metadata(path: Path, verdict: ContinuationVerdict) -> dict[str, object]:
    task_key = path.name
    return {
        "path": str(path),
        "task_key": task_key,
        **verdict.model_dump(mode="json"),
    }


def compact_previous_turn_context(verdict: ContinuationVerdict) -> tuple[str, ...]:
    instructions = verdict.next_turn_instructions or "none"
    return (
        f"verdict: {verdict.verdict}",
        f"summary: {verdict.summary}",
        "completed_finding_ids: " + _compact_tuple(verdict.completed_finding_ids),
        "remaining_finding_ids: " + _compact_tuple(verdict.remaining_finding_ids),
        "resolutions: " + _compact_resolutions(verdict.resolutions),
        f"next_turn_instructions: {instructions}",
    )


def _compact_tuple(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _compact_resolutions(values: tuple[FindingResolution, ...]) -> str:
    if not values:
        return "none"
    return ", ".join(f"{item.finding_id}:{item.state}" for item in values)


def finite_positive(value: float, *, field_name: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be a finite value greater than zero")
    return value
