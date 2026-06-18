from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from review_gauntlet.models import ReviewPlan


class CellState(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class ReviewCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    file_path: str
    rule_id: str
    slice_id: str
    state: CellState = CellState.PENDING
    content_digest: str = ""


TERMINAL_CELL_STATES = {CellState.REVIEWED}


def cell_id_for(file_path: str, rule_id: str, slice_id: str) -> str:
    digest = hashlib.sha256(f"{slice_id}\0{rule_id}\0{file_path}".encode()).hexdigest()[:16]
    return f"RGC-{digest}"


def cells_from_plan(
    plan: ReviewPlan, file_digests: dict[str, str] | None = None
) -> tuple[ReviewCell, ...]:
    digests = file_digests or {}
    cells: list[ReviewCell] = []
    for review_slice in plan.slices:
        for file_path in review_slice.files:
            for check in review_slice.checks:
                cells.append(
                    ReviewCell(
                        id=cell_id_for(file_path, check.id, review_slice.id),
                        file_path=file_path,
                        rule_id=check.id,
                        slice_id=review_slice.id,
                        content_digest=digests.get(file_path, ""),
                    )
                )
    return tuple(sorted(cells, key=lambda cell: cell.id))
