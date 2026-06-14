import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main


@pytest.fixture(autouse=True)
def isolate_global_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


def test_config_preset_list_outputs_bundled_preset_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["config", "preset", "list"])

    assert capsys.readouterr().out.splitlines() == ["claude", "opencode", "codex"]


def test_config_preset_show_outputs_preset_content(capsys: pytest.CaptureFixture[str]) -> None:
    main(["config", "preset", "show", "opencode"])

    output = capsys.readouterr().out
    assert '"command": "opencode"' in output
    assert "configs/review-gauntlet" not in output


def test_config_init_project_force_and_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["config", "init", str(tmp_path), "--preset", "opencode", "--dry-run"])
    dry_run_output = capsys.readouterr().out
    assert "would write" in dry_run_output
    assert str(tmp_path / ".review-gauntlet" / "config.jsonc") in dry_run_output
    assert '"command": "opencode"' in dry_run_output
    assert "--- config contents ---" in dry_run_output
    assert not (tmp_path / ".review-gauntlet").exists()

    main(["config", "init", str(tmp_path), "--preset", "opencode", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    config_path = tmp_path / ".review-gauntlet" / "config.jsonc"
    assert data["written"] is True
    assert config_path.exists()

    with pytest.raises(SystemExit) as exc_info:
        main(["config", "init", str(tmp_path), "--preset", "codex"])
    assert exc_info.value.code == 64
    assert "already exists" in capsys.readouterr().err

    main(["config", "init", str(tmp_path), "--preset", "codex", "--force"])
    assert '"command": "codex"' in config_path.read_text(encoding="utf-8")


def test_config_init_dry_run_json_includes_contents(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(
        [
            "config",
            "init",
            str(tmp_path),
            "--preset",
            "opencode",
            "--dry-run",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["written"] is False
    assert str(tmp_path / ".review-gauntlet" / "config.jsonc") == data["path"]
    assert '"command": "opencode"' in data["contents"]
    assert not (tmp_path / ".review-gauntlet").exists()


def test_config_init_global_and_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    xdg_home = tmp_path / "xdg-home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))

    main(["config", "init", str(tmp_path), "--global", "--preset", "claude", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert Path(data["path"]) == xdg_home / "review-gauntlet" / "config.jsonc"
    assert Path(data["path"]).exists()

    output = tmp_path / "custom" / "config.jsonc"
    main(["config", "init", str(tmp_path), "--output", str(output), "--preset", "opencode"])
    assert output.exists()


def test_config_validate_and_effective_outputs_merged_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    xdg_home = tmp_path / "xdg-home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    global_config = xdg_home / "review-gauntlet" / "config.jsonc"
    global_config.parent.mkdir(parents=True)
    global_config.write_text(
        '{"adapter":{"type":"command","command":"global","args":["old"],"env":{"A":"1"}}}',
        encoding="utf-8",
    )
    project_config = tmp_path / ".review-gauntlet" / "config.jsonc"
    project_config.parent.mkdir(parents=True)
    project_config.write_text(
        '{"adapter":{"command":"project","args":["new"],"env":{"B":"2"}}}',
        encoding="utf-8",
    )

    main(["config", "validate", str(tmp_path), "--format", "json"])
    valid = json.loads(capsys.readouterr().out)
    assert valid["valid"] is True
    assert valid["adapter_command"] == "project"

    main(["config", "effective", str(tmp_path), "--format", "json"])
    effective = json.loads(capsys.readouterr().out)
    assert effective["adapter"]["command"] == "project"
    assert effective["adapter"]["args"] == ["new"]
    assert effective["adapter"]["env"] == {"A": "1", "B": "2"}


def test_config_validate_failure_and_explicit_absolute_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path.parent / "outside-config.jsonc"
    outside.write_text('{"adapter":{"type":"command","command":"outside"}}', encoding="utf-8")

    main(["config", "validate", str(tmp_path), "--config", str(outside), "--format", "json"])
    assert json.loads(capsys.readouterr().out)["adapter_command"] == "outside"

    bad = tmp_path / "bad.jsonc"
    bad.write_text('{"adapter":{"type":"command","command":"bad command"}}', encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        main(["config", "validate", str(tmp_path), "--config", str(bad)])
    assert exc_info.value.code == 64
    assert "shell string" in capsys.readouterr().err
