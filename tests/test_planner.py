from review_gauntlet.models import FileCategory, FileRecord, Inventory
from review_gauntlet.planner import build_matrix, build_plan


def test_build_plan_adds_risk_specific_checks() -> None:
    inventory = Inventory(
        root="/repo",
        files=(
            FileRecord(
                path="src/pkg/core.py",
                category=FileCategory.PYTHON,
                risk_tags=("file-safety", "data-contract"),
            ),
            FileRecord(
                path="scripts/run", category=FileCategory.SHELL, risk_tags=("process-exec",)
            ),
            FileRecord(path="README.md", category=FileCategory.DOCS),
        ),
    )

    plan = build_plan(inventory)
    checks_by_slice = {slice.id: {check.id for check in slice.checks} for slice in plan.slices}

    assert {"data-validation", "path-safety", "test-evidence"}.issubset(
        checks_by_slice["python-runtime"]
    )
    assert {"cli-contract", "process-exec"}.issubset(checks_by_slice["shell-entrypoints"])
    assert checks_by_slice["docs"] == {"docs-accuracy"}

    matrix = build_matrix(plan)
    assert not matrix.is_complete
    assert len(matrix.rows) == sum(len(slice.checks) for slice in plan.slices)
