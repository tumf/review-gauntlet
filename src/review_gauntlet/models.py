from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FileCategory(StrEnum):
    PYTHON = "python"
    TEST = "test"
    SHELL = "shell"
    NOTIFIER = "notifier"
    CI = "ci"
    CONFIG = "config"
    DOCS = "docs"
    OTHER = "other"


class MatrixStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    COVERED = "covered"
    BLOCKED = "blocked"


class FileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    category: FileCategory
    risk_tags: tuple[str, ...] = ()


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str
    files: tuple[FileRecord, ...]


class ReviewCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    why: str


class ReviewSlice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    files: tuple[str, ...]
    checks: tuple[ReviewCheck, ...]


class ReviewPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str
    slices: tuple[ReviewSlice, ...]


class MatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slice_id: str
    check_id: str
    status: MatrixStatus = MatrixStatus.NEEDS_REVIEW
    evidence: str | None = None


class ReviewMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str
    rows: tuple[MatrixRow, ...]

    @property
    def is_complete(self) -> bool:
        return all(row.status == MatrixStatus.COVERED for row in self.rows)


def display_root(path: Path) -> str:
    return str(path.resolve())
