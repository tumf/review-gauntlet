from review_gauntlet.models import ReviewCheck, ReviewPlan, ReviewSlice
from review_gauntlet.review_cells import TERMINAL_CELL_STATES, CellState, cell_id_for, cells_from_plan


def test_review_cells_are_deterministic_from_plan() -> None:
    plan = ReviewPlan(
        root="/repo",
        slices=(
            ReviewSlice(
                id="docs",
                title="Docs",
                files=("README.md",),
                checks=(ReviewCheck(id="docs-accuracy", title="Docs", why="accurate"),),
            ),
        ),
    )

    cells = cells_from_plan(plan, {"README.md": "digest"})

    assert len(cells) == 1
    assert cells[0].id == cell_id_for("README.md", "docs-accuracy", "docs")
    assert cells[0].content_digest == "digest"


def test_cell_state_is_two_phase_model() -> None:
    assert tuple(CellState) == (CellState.PENDING, CellState.REVIEWED)
    assert TERMINAL_CELL_STATES == {CellState.REVIEWED}
