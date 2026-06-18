import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.review_cells import CellState
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import target_digest


def test_finalize_writes_checkpoint_with_two_phase_states(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    store = SessionStore(tmp_path)
    session_id = store.active_session_id()
    for row in store.list_cells(session_id):
        store.update_cell_state(session_id, str(row["cell_id"]), CellState.REVIEWED)
    store.create_run(session_id, target_digest(tmp_path))

    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    checkpoint_path = tmp_path / str(data["checkpoint_dir"])
    status = json.loads((checkpoint_path / "status.json").read_text(encoding="utf-8"))
    assert status["coverage"]
    assert data["session_state"] == "finalized"


def test_finalize_blocks_dirty_review_universe_without_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    with pytest.raises(SystemExit):
        main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is False
