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
