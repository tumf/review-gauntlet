from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.review_cells import ReviewCell


class ReviewAdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cell_id: str
    comments: tuple[OCRComment, ...] = ()


class FakeReviewAdapter:
    def __init__(self, fixtures_path: Path | None = None) -> None:
        self._fixtures = _load_fixtures(fixtures_path) if fixtures_path else {}

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        raw_comments = self._fixtures.get(cell.id) or self._fixtures.get(cell.file_path) or []
        comments = tuple(OCRComment.model_validate(comment) for comment in raw_comments)
        return ReviewAdapterResult(cell_id=cell.id, comments=comments)


def _load_fixtures(path: Path) -> dict[str, list[dict[str, object]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fake review fixture must be a JSON object")
    raw = cast(dict[str, object], data)
    result: dict[str, list[dict[str, object]]] = {}
    for key, value in raw.items():
        if not isinstance(value, list):
            raise ValueError("fake review fixture maps strings to comment lists")
        comments: list[dict[str, object]] = []
        for item in cast(list[object], value):
            if not isinstance(item, dict):
                raise ValueError("fake review fixture comments must be objects")
            comments.append(cast(dict[str, object], item))
        result[key] = comments
    return result
