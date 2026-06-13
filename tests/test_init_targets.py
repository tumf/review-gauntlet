import json
import subprocess
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import file_digests, review_universe_files, target_digest


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "unchanged.py").write_text("print('unchanged')\n", encoding="utf-8")
    _git(root, "add", "unchanged.py")
    _git(root, "commit", "-m", "initial")


def _cell_paths(root: Path) -> set[str]:
    return {str(row["file_path"]) for row in SessionStore(root).list_cells()}


def test_default_init_without_checkpoint_uses_all_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "staged.py").write_text("print('staged')\n", encoding="utf-8")
    (tmp_path / "unstaged.py").write_text("print('unstaged')\n", encoding="utf-8")
    (tmp_path / "untracked.py").write_text("print('untracked')\n", encoding="utf-8")
    _git(tmp_path, "add", "staged.py")
    _git(tmp_path, "add", "unstaged.py")
    (tmp_path / "unstaged.py").write_text("print('unstaged changed')\n", encoding="utf-8")

    main(["init", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["cell_count"] > 0
    assert {"staged.py", "unstaged.py", "untracked.py", "unchanged.py"}.issubset(
        _cell_paths(tmp_path)
    )


def test_explicit_worktree_matches_default_workspace_diff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "changed.py").write_text("print('changed')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_changed.py").write_text(
        "def test_changed(): pass\n", encoding="utf-8"
    )
    (tmp_path / "app.spec.ts").write_text("test('changed', () => {})\n", encoding="utf-8")
    (tmp_path / "foo_test.rs").write_text("#[test]\nfn it_works() {}\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "Cargo.lock").write_text("# lock\n", encoding="utf-8")

    main(["init", str(tmp_path), "--worktree", "--format", "json"])

    assert json.loads(capsys.readouterr().out)["cell_count"] > 0
    assert _cell_paths(tmp_path) == {"changed.py"}


def test_package_only_worktree_changes_create_no_review_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "Cargo.lock").write_text("# lock\n", encoding="utf-8")

    main(["init", str(tmp_path), "--worktree", "--format", "json"])

    assert json.loads(capsys.readouterr().out)["cell_count"] == 0
    assert _cell_paths(tmp_path) == set()


def test_branch_range_init_scopes_to_changed_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "feature.py").write_text("print('feature')\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"dependencies": {}}\n', encoding="utf-8")
    (tmp_path / "go.sum").write_text("example.com/mod v1.0.0 h1:abc\n", encoding="utf-8")
    _git(tmp_path, "add", "feature.py", "package.json", "go.sum")
    _git(tmp_path, "commit", "-m", "feature")
    head = _git(tmp_path, "rev-parse", "HEAD")

    main(["init", str(tmp_path), "--from", base, "--to", head, "--format", "json"])

    assert json.loads(capsys.readouterr().out)["cell_count"] > 0
    assert _cell_paths(tmp_path) == {"feature.py"}


def test_default_init_uses_latest_checkpoint_base_to_head(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    base = _git(tmp_path, "rev-parse", "HEAD")
    _write_checkpoint(tmp_path, base)
    (tmp_path / "after.py").write_text("print('after')\n", encoding="utf-8")
    _git(tmp_path, "add", "after.py")
    _git(tmp_path, "commit", "-m", "after")

    main(["init", str(tmp_path), "--format", "json"])

    assert json.loads(capsys.readouterr().out)["cell_count"] > 0
    metadata = SessionStore(tmp_path).session_metadata()
    assert metadata["target"]["kind"] == "branch"
    assert metadata["target"]["base_ref"] == base
    assert _cell_paths(tmp_path) == {"after.py"}


def test_default_init_rejects_invalid_latest_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path, _git(tmp_path, "rev-parse", "HEAD"), usable=False)

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "not usable" in capsys.readouterr().err


def test_default_init_rejects_unsupported_checkpoint_schema_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path, _git(tmp_path, "rev-parse", "HEAD"), schema_version=2)

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "schema_version" in capsys.readouterr().err


def test_default_init_rejects_non_string_review_base_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path, None)

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "review_base_commit must be a string" in capsys.readouterr().err


def test_default_init_rejects_non_string_checkpoint_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(
        tmp_path,
        _git(tmp_path, "rev-parse", "HEAD"),
        checkpoint_id=123,
        companion_checkpoint_id="123",
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "checkpoint_id must be a string" in capsys.readouterr().err


def test_default_init_rejects_missing_payload_array(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    checkpoint_dir = tmp_path / ".review-gauntlet" / "checkpoints" / "RGC-test"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    latest_pointer = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    latest_pointer.write_text("RGC-test", encoding="utf-8")
    status = {
        "schema_version": 1,
        "checkpoint_id": "RGC-test",
        "checkpoint_state": "complete",
        "usable_as_review_base": True,
        "review_base_commit": _git(tmp_path, "rev-parse", "HEAD"),
    }
    (checkpoint_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
    (checkpoint_dir / "findings.json").write_text(
        json.dumps({"checkpoint_id": "RGC-test"}), encoding="utf-8"
    )
    (checkpoint_dir / "events.json").write_text(
        json.dumps({"checkpoint_id": "RGC-test", "events": []}), encoding="utf-8"
    )
    (checkpoint_dir / "summary.md").write_text("# checkpoint\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "internally inconsistent" in capsys.readouterr().err


def test_default_init_rejects_checkpoint_payload_entries_without_matching_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path, _git(tmp_path, "rev-parse", "HEAD"))
    checkpoint_dir = tmp_path / ".review-gauntlet" / "checkpoints" / "RGC-test"
    (checkpoint_dir / "findings.json").write_text(
        json.dumps({"checkpoint_id": "RGC-test", "findings": [None]}), encoding="utf-8"
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "internally inconsistent" in capsys.readouterr().err


def test_default_init_rejects_unresolvable_checkpoint_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path, "deadbeef")

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "does not resolve" in capsys.readouterr().err


def test_default_init_rejects_mutable_checkpoint_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path, "HEAD")

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "resolved commit SHA" in capsys.readouterr().err


def test_default_init_ignores_unsafe_latest_checkpoint_pointer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    checkpoint_root = tmp_path / ".review-gauntlet" / "checkpoints"
    checkpoint_root.mkdir(parents=True)
    (checkpoint_root / "latest").write_text("../outside\n", encoding="utf-8")
    (tmp_path / ".review-gauntlet" / "outside").mkdir()
    ((tmp_path / ".review-gauntlet" / "outside") / "status.json").write_text("{}", encoding="utf-8")

    main(["init", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["cell_count"] > 0
    assert SessionStore(tmp_path).session_metadata()["target"]["kind"] == "all"


def test_default_init_rejects_non_ancestor_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    old = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "other.py").write_text("print('other')\n", encoding="utf-8")
    _git(tmp_path, "add", "other.py")
    _git(tmp_path, "commit", "-m", "other")
    _git(tmp_path, "checkout", "--orphan", "newroot")
    (tmp_path / "fresh.py").write_text("print('fresh')\n", encoding="utf-8")
    _git(tmp_path, "add", "fresh.py")
    _git(tmp_path, "commit", "-m", "fresh")
    _write_checkpoint(tmp_path, old)

    with pytest.raises(SystemExit) as excinfo:
        main(["init", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "not an ancestor" in capsys.readouterr().err


def test_commit_init_scopes_to_commit_files_and_records_fixed_head(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "commit_only.py").write_text("print('commit')\n", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project />\n", encoding="utf-8")
    _git(tmp_path, "add", "commit_only.py", "Cargo.toml", "pom.xml")
    _git(tmp_path, "commit", "-m", "commit only")
    commit = _git(tmp_path, "rev-parse", "HEAD")

    main(["init", str(tmp_path), "--commit", commit, "--format", "json"])

    assert json.loads(capsys.readouterr().out)["cell_count"] > 0
    assert _cell_paths(tmp_path) == {"commit_only.py"}
    metadata = SessionStore(tmp_path).session_metadata(SessionStore(tmp_path).active_session_id())
    assert metadata["target"]["kind"] == "commit"
    assert metadata["target"]["head_mode"] == "fixed"


def test_init_then_all_init_allows_overlapping_review_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "changed.py").write_text("print('changed')\n", encoding="utf-8")

    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    first = json.loads(capsys.readouterr().out)
    assert first["cell_count"] > 0

    main(["init", str(tmp_path), "--all", "--format", "json"])
    second = json.loads(capsys.readouterr().out)
    assert second["cell_count"] > first["cell_count"]
    assert second["session_id"] != first["session_id"]

    main(["status", str(tmp_path), "--format", "json"])
    status = json.loads(capsys.readouterr().out)
    assert status["session_id"] == second["session_id"]
    assert status["coverage"] == {"pending": second["cell_count"]}


def test_all_init_uses_full_inventory_and_exclusions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "changed.py").write_text("print('changed')\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "usage.md").write_text("# usage\n", encoding="utf-8")
    (tmp_path / "openspec" / "specs").mkdir(parents=True)
    (tmp_path / "openspec" / "specs" / "spec.md").write_text("# spec\n", encoding="utf-8")
    (tmp_path / "foo_test.go").write_text("package main\n", encoding="utf-8")
    (tmp_path / "foo_test.rs").write_text("#[test]\nfn it_works() {}\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "Cargo.lock").write_text("# lock\n", encoding="utf-8")
    state_dir = tmp_path / ".review-gauntlet"
    state_dir.mkdir()
    (state_dir / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")

    main(["init", str(tmp_path), "--all", "--format", "json"])

    assert json.loads(capsys.readouterr().out)["cell_count"] > 0
    paths = _cell_paths(tmp_path)
    assert {"changed.py", "unchanged.py"}.issubset(paths)
    assert "docs/usage.md" not in paths
    assert "openspec/specs/spec.md" not in paths
    assert "foo_test.go" not in paths
    assert "foo_test.rs" not in paths
    assert "uv.lock" not in paths
    assert "package.json" not in paths
    assert "Cargo.lock" not in paths
    assert ".review-gauntlet/ignored.py" not in paths


def test_review_universe_and_file_digests_omit_package_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")

    universe_paths = {
        path.relative_to(tmp_path).as_posix() for path in review_universe_files(tmp_path)
    }
    digest_paths = set(file_digests(tmp_path))
    baseline_target_digest = target_digest(tmp_path)
    (tmp_path / "uv.lock").write_text("version = 2\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")

    assert universe_paths == {"src/app.py"}
    assert digest_paths == {"src/app.py"}
    assert target_digest(tmp_path) == baseline_target_digest


@pytest.mark.parametrize("flag", ["--from", "--to", "--commit", "--worktree", "--all"])
def test_review_rejects_target_flags(
    tmp_path: Path, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    main(["init", str(tmp_path), "--all", "--format", "json"])
    capsys.readouterr()
    argv = ["review", str(tmp_path), flag]
    if flag in {"--from", "--to", "--commit"}:
        argv.append("HEAD")

    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 64


def test_review_still_advances_one_initialized_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    fixture = tmp_path / ".review-gauntlet" / "fixtures" / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}", encoding="utf-8")
    main(["init", str(tmp_path), "--all", "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["reviewed_cells"] == 1
    assert data["run_count"] == 1


def _write_checkpoint(
    root: Path,
    base: object,
    *,
    usable: bool = True,
    schema_version: int = 1,
    checkpoint_id: object = "RGC-test",
    companion_checkpoint_id: object | None = None,
) -> None:
    checkpoint_dir = root / ".review-gauntlet" / "checkpoints" / str(checkpoint_id)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    latest_pointer = root / ".review-gauntlet" / "checkpoints" / "latest"
    latest_pointer.write_text(str(checkpoint_id), encoding="utf-8")
    status = {
        "schema_version": schema_version,
        "checkpoint_id": checkpoint_id,
        "checkpoint_state": "complete",
        "usable_as_review_base": usable,
        "review_base_commit": base,
    }
    (checkpoint_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")
    (checkpoint_dir / "findings.json").write_text(
        json.dumps(
            {
                "checkpoint_id": companion_checkpoint_id
                if companion_checkpoint_id is not None
                else checkpoint_id,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    (checkpoint_dir / "events.json").write_text(
        json.dumps(
            {
                "checkpoint_id": companion_checkpoint_id
                if companion_checkpoint_id is not None
                else checkpoint_id,
                "events": [],
            }
        ),
        encoding="utf-8",
    )
    (checkpoint_dir / "summary.md").write_text("# checkpoint\n", encoding="utf-8")
