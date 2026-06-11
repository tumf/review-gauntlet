import subprocess
from pathlib import Path

from review_gauntlet.inventory import build_inventory
from review_gauntlet.models import FileCategory


def test_build_inventory_classifies_project_files(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "core.py").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text("", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    script = tmp_path / "scripts" / "run"
    script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    script.chmod(0o755)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    inventory = build_inventory(tmp_path)
    by_path = {file.path: file for file in inventory.files}

    assert by_path["src/pkg/core.py"].category == FileCategory.PYTHON
    assert "file-safety" in by_path["src/pkg/core.py"].risk_tags
    assert by_path["tests/test_core.py"].category == FileCategory.TEST
    assert by_path["scripts/run"].category == FileCategory.SHELL
    assert by_path[".github/workflows/ci.yml"].category == FileCategory.CI
    assert by_path["README.md"].category == FileCategory.DOCS


def test_build_inventory_excludes_generated_artifacts(tmp_path: Path) -> None:
    included_files = [
        "src/pkg/core.py",
        "tests/test_core.py",
        "README.md",
        "pyproject.toml",
    ]
    excluded_files = [
        ".review-gauntlet/runs/run-1/prompt.md",
        ".ruff_cache/cache.json",
        ".pyright/typeshed-fallback/stdlib.json",
        ".mypy_cache/3.11/core.meta.json",
        "build/lib/pkg/core.py",
        "dist/pkg.whl",
        "wheels/pkg.whl",
        "pkg.egg-info/PKG-INFO",
        ".coverage",
        "htmlcov/index.html",
        ".DS_Store",
        ".idea/workspace.xml",
        ".vscode/settings.json",
    ]
    for relative in [*included_files, *excluded_files]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated or source\n", encoding="utf-8")

    inventory = build_inventory(tmp_path)
    inventory_paths = {file.path for file in inventory.files}

    assert set(included_files) <= inventory_paths
    assert not (set(excluded_files) & inventory_paths)


def test_git_inventory_excludes_review_gauntlet_state(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / ".gitignore").write_text("ignored.log\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".review-gauntlet" / "runs").mkdir(parents=True)
    (tmp_path / ".review-gauntlet" / "runs" / "prompt.md").write_text(
        "generated\n", encoding="utf-8"
    )
    (tmp_path / "ignored.log").write_text("ignored\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", ".gitignore", "src/app.py"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    inventory = build_inventory(tmp_path)
    inventory_paths = {file.path for file in inventory.files}

    assert "src/app.py" in inventory_paths
    assert ".gitignore" in inventory_paths
    assert ".review-gauntlet/runs/prompt.md" not in inventory_paths
    assert "ignored.log" not in inventory_paths


def test_inventory_omits_review_run_artifacts(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    run_dir = tmp_path / ".review-gauntlet" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "prompt.md").write_text("prompt\n", encoding="utf-8")
    (run_dir / "command.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "verdict.md").write_text("verdict\n", encoding="utf-8")
    (tmp_path / ".review-gauntlet" / "ledger.jsonl").write_text("{}\n", encoding="utf-8")

    inventory = build_inventory(tmp_path)
    inventory_paths = {file.path for file in inventory.files}

    assert "src/app.py" in inventory_paths
    assert all(not path.startswith(".review-gauntlet/") for path in inventory_paths)
