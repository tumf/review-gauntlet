from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from review_gauntlet.inventory import normalize_repository_relative_path
from review_gauntlet.ocr_rules import OCRComment


class FindingState(StrEnum):
    UNTRIAGED = "untriaged"
    CONFIRMED = "confirmed"
    FIXED_PENDING_VERIFICATION = "fixed_pending_verification"
    FIXED_VERIFIED = "fixed_verified"
    FALSE_POSITIVE = "false_positive"
    WAIVED = "waived"
    ACCEPTED_RISK = "accepted_risk"
    REOPENED = "reopened"


TERMINAL_FINDING_STATES = {
    FindingState.FIXED_VERIFIED,
    FindingState.FALSE_POSITIVE,
    FindingState.WAIVED,
    FindingState.ACCEPTED_RISK,
}

ALLOWED_TRANSITIONS: dict[FindingState, set[FindingState]] = {
    FindingState.UNTRIAGED: {
        FindingState.CONFIRMED,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
        FindingState.FIXED_PENDING_VERIFICATION,
    },
    FindingState.CONFIRMED: {
        FindingState.FIXED_PENDING_VERIFICATION,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
    },
    FindingState.REOPENED: {
        FindingState.CONFIRMED,
        FindingState.FIXED_PENDING_VERIFICATION,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
    },
    FindingState.FIXED_PENDING_VERIFICATION: {
        FindingState.FIXED_VERIFIED,
        FindingState.REOPENED,
    },
    FindingState.FIXED_VERIFIED: set(),
    FindingState.FALSE_POSITIVE: set(),
    FindingState.WAIVED: set(),
    FindingState.ACCEPTED_RISK: set(),
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
