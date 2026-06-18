import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.cli import build_parser, main
from review_gauntlet.review_cells import CellState, ReviewCell
from review_gauntlet.session_store import SessionStore


def test_verify_fixes_command_is_removed() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify-fixes", "--help"])
    assert exc_info.value.code == 64


def test_resolve_parser_accepts_parallel_and_config() -> None:
    args = build_parser().parse_args(
        ["resolve", ".", "--parallel", "4", "--max-turns", "2", "--config", "rg.toml"]
    )
    assert args.command == "resolve"
    assert args.parallel == 4
    assert args.max_turns == 2
    assert args.config == Path("rg.toml")


def test_resolve_noops_when_no_open_findings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    config = tmp_path / "review-gauntlet.toml"
    config.write_text('[adapter]\ncommand = "python"\nargs = ["-c", "print(1)"]\n', encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    store = SessionStore(tmp_path)
    for row in store.list_cells():
        store.update_cell_state(store.active_session_id(), str(row["cell_id"]), CellState.REVIEWED)

    main(["resolve", str(tmp_path), "--config", str(config), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["resolved_finding_ids"] == []


def test_store_lists_open_findings_grouped_source(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "d", "target": {}},
        (ReviewCell(id="RGC-1", file_path="a.py", rule_id="security", slice_id="s"),),
    )
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(session_id, finding_id, fingerprint, state, path, rule_id, content, metadata)
            values ('RGS-test', 'RGF-0001', 'fp', 'open', 'a.py', 'security', 'issue', '{}')
            """
        )
        conn.execute(
            """
            insert into findings(session_id, finding_id, fingerprint, state, path, rule_id, content, metadata)
            values ('RGS-test', 'RGF-0002', 'fp2', 'confirmed', 'a.py', 'security', 'done', '{}')
            """
        )

    rows = store.list_open_findings("RGS-test")

    assert [str(row["finding_id"]) for row in rows] == ["RGF-0001"]
