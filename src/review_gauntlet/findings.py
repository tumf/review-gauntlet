from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from review_gauntlet.inventory import normalize_repository_relative_path
from review_gauntlet.ocr_rules import OCRComment


class FindingState(StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


TERMINAL_FINDING_STATES = {
    FindingState.CONFIRMED,
    FindingState.DISMISSED,
}

ALLOWED_TRANSITIONS: dict[FindingState, set[FindingState]] = {
    FindingState.OPEN: {FindingState.CONFIRMED, FindingState.DISMISSED},
    FindingState.CONFIRMED: set(),
    FindingState.DISMISSED: set(),
}


class NormalizedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fingerprint: str
    path: str
    rule_id: str
    content: str
    suggestion_code: str = ""
    existing_code: str = ""
    start_line: int = 0
    end_line: int = 0
    thinking: str | None = None
    imprecise: bool = False
    dismiss_reason: str | None = None


class FindingResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str
    state: Literal["confirmed", "dismissed"]
    dismiss_reason: str | None = None

    @field_validator("finding_id")
    @classmethod
    def validate_finding_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("finding_id must be a non-empty string")
        return text

    @field_validator("dismiss_reason", mode="before")
    @classmethod
    def validate_dismiss_reason(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("dismiss_reason must be a string or null")
        text = value.strip()
        return text or None


def normalize_ocr_comment(
    comment: OCRComment,
    *,
    repository_id: str,
    base_target: str,
    rule_id: str,
    ruleset_digest: str,
) -> NormalizedFinding:
    normalized_path = normalize_repository_relative_path(comment.path)
    normalized_claim = " ".join(comment.content.split()).lower()
    code_anchor = " ".join((comment.existing_code or comment.suggestion_code).split()).lower()
    fingerprint_payload = "\0".join(
        [
            repository_id,
            base_target,
            normalized_path,
            rule_id,
            normalized_claim,
            code_anchor,
            ruleset_digest,
        ]
    )
    fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
    return NormalizedFinding(
        fingerprint=fingerprint,
        path=normalized_path,
        rule_id=rule_id,
        content=comment.content,
        suggestion_code=comment.suggestion_code,
        existing_code=comment.existing_code,
        start_line=comment.start_line,
        end_line=comment.end_line,
        thinking=comment.thinking,
        imprecise=comment.imprecise,
    )


def assert_transition_allowed(current: FindingState, desired: FindingState) -> None:
    if desired not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid finding transition: {current} -> {desired}")
