from __future__ import annotations

from collections import defaultdict

from review_gauntlet.models import (
    FileCategory,
    Inventory,
    MatrixRow,
    ReviewCheck,
    ReviewMatrix,
    ReviewPlan,
    ReviewSlice,
)

CHECK_LIBRARY: dict[str, ReviewCheck] = {
    "path-safety": ReviewCheck(
        id="path-safety",
        title="Path traversal and file overwrite safety",
        why="File-backed tools must not escape the repo or corrupt user data.",
    ),
    "data-validation": ReviewCheck(
        id="data-validation",
        title="Boundary data validation",
        why="Structured inputs need explicit validation and predictable error behavior.",
    ),
    "cli-contract": ReviewCheck(
        id="cli-contract",
        title="Agent-friendly CLI contract",
        why="Agents need stable exit codes, non-interactive behavior, and structured output.",
    ),
    "process-exec": ReviewCheck(
        id="process-exec",
        title="Process execution failure handling",
        why="Subprocess failures should be bounded, observable, and non-surprising.",
    ),
    "secret-handling": ReviewCheck(
        id="secret-handling",
        title="Secret and environment handling",
        why="Review outputs and child processes must not leak credentials.",
    ),
    "test-evidence": ReviewCheck(
        id="test-evidence",
        title="Regression and edge-case test evidence",
        why="A review finding is not closed until an automated check covers it.",
    ),
    "ci-reproducibility": ReviewCheck(
        id="ci-reproducibility",
        title="CI reproducibility",
        why="Local and remote checks should run the same commands.",
    ),
    "docs-accuracy": ReviewCheck(
        id="docs-accuracy",
        title="Documentation accuracy",
        why="Docs should match the shipped command surface and constraints.",
    ),
}

CATEGORY_SLICE_IDS = {
    FileCategory.PYTHON: "python-runtime",
    FileCategory.TEST: "tests",
    FileCategory.SHELL: "shell-entrypoints",
    FileCategory.NOTIFIER: "notifiers",
    FileCategory.CI: "ci",
    FileCategory.CONFIG: "config",
    FileCategory.DOCS: "docs",
    FileCategory.OTHER: "other",
}

SLICE_TITLES = {
    "python-runtime": "Python runtime code",
    "tests": "Test suite",
    "shell-entrypoints": "Shell entrypoints",
    "notifiers": "Notifier adapters",
    "ci": "Continuous integration",
    "config": "Project configuration",
    "docs": "Documentation",
    "other": "Other files",
}


def build_plan(inventory: Inventory) -> ReviewPlan:
    grouped: dict[str, list[str]] = defaultdict(list)
    checks: dict[str, set[str]] = defaultdict(set)
    for file in inventory.files:
        slice_id = CATEGORY_SLICE_IDS[file.category]
        grouped[slice_id].append(file.path)
        checks[slice_id].update(check_ids_for_file(file.category, file.risk_tags))

    slices = tuple(
        ReviewSlice(
            id=slice_id,
            title=SLICE_TITLES[slice_id],
            files=tuple(sorted(files)),
            checks=tuple(CHECK_LIBRARY[check_id] for check_id in sorted(checks[slice_id])),
        )
        for slice_id, files in sorted(grouped.items())
    )
    return ReviewPlan(root=inventory.root, slices=slices)


def check_ids_for_file(category: FileCategory, risk_tags: tuple[str, ...]) -> set[str]:
    ids: set[str] = set()
    if category == FileCategory.PYTHON:
        ids.update({"data-validation", "test-evidence"})
    if category == FileCategory.TEST:
        ids.add("test-evidence")
    if category == FileCategory.SHELL:
        ids.update({"cli-contract", "process-exec"})
    if category == FileCategory.NOTIFIER:
        ids.update({"process-exec", "secret-handling", "test-evidence"})
    if category == FileCategory.CI:
        ids.add("ci-reproducibility")
    if category == FileCategory.CONFIG:
        ids.update({"ci-reproducibility", "data-validation"})
    if category == FileCategory.DOCS:
        ids.add("docs-accuracy")
    if "file-safety" in risk_tags:
        ids.add("path-safety")
    if "cli-contract" in risk_tags:
        ids.add("cli-contract")
    if not ids:
        ids.add("docs-accuracy")
    return ids


def build_matrix(plan: ReviewPlan) -> ReviewMatrix:
    rows = tuple(
        MatrixRow(slice_id=slice.id, check_id=check.id)
        for slice in plan.slices
        for check in slice.checks
    )
    return ReviewMatrix(root=plan.root, rows=rows)
