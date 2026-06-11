from __future__ import annotations

import os
import subprocess
from pathlib import Path

from review_gauntlet.models import FileCategory, FileRecord, Inventory, display_root

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".review-gauntlet",
    ".ruff_cache",
    ".pyright",
    ".mypy_cache",
    "build",
    "dist",
    "wheels",
    "htmlcov",
    ".idea",
    ".vscode",
}
EXCLUDED_FILE_NAMES = {".coverage", ".DS_Store"}
EXCLUDED_DIR_SUFFIXES = {".egg-info"}
CONFIG_NAMES = {
    ".editorconfig",
    ".gitignore",
    ".python-version",
    "Makefile",
    "pyproject.toml",
    "prek.toml",
    "uv.lock",
}


def build_inventory(root: Path) -> Inventory:
    repo_root = root.resolve()
    files = tuple(classify_file(path, repo_root) for path in list_project_files(repo_root))
    return Inventory(root=display_root(repo_root), files=files)


def build_inventory_for_paths(root: Path, relative_paths: tuple[str, ...]) -> Inventory:
    repo_root = root.resolve()
    files = tuple(
        classify_file(repo_root / relative, repo_root)
        for relative in sorted(relative_paths)
        if should_include_relative_path(relative) and (repo_root / relative).is_file()
    )
    return Inventory(root=display_root(repo_root), files=files)


def list_project_files(root: Path) -> list[Path]:
    tracked = git_file_list(root)
    if tracked is not None:
        return sorted(root / path for path in tracked if should_include_relative_path(path))
    return sorted(path for path in root.rglob("*") if should_include_path(path, root))


def git_file_list(root: Path) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [line for line in result.stdout.splitlines() if line]


def should_include_relative_path(relative: str | Path) -> bool:
    path = Path(relative)
    return not any(
        part in EXCLUDED_DIR_NAMES
        or part in EXCLUDED_FILE_NAMES
        or any(part.endswith(suffix) for suffix in EXCLUDED_DIR_SUFFIXES)
        for part in path.parts
    )


def should_include_path(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    return should_include_relative_path(path.relative_to(root))


def classify_file(path: Path, root: Path) -> FileRecord:
    relative = path.relative_to(root).as_posix()
    category = file_category(path, relative)
    return FileRecord(
        path=relative, category=category, risk_tags=risk_tags(path, relative, category)
    )


def file_category(path: Path, relative: str) -> FileCategory:
    parts = Path(relative).parts
    if len(parts) >= 2 and parts[0] == ".agentloop" and parts[1] == "notifiers":
        return FileCategory.NOTIFIER
    if relative.startswith("tests/") or relative.startswith("test/"):
        return FileCategory.TEST
    if relative.startswith(".github/workflows/"):
        return FileCategory.CI
    if path.suffix == ".py":
        return FileCategory.PYTHON
    if path.suffix in {".sh", ".bash"} or relative.startswith("scripts/") or is_executable(path):
        return FileCategory.SHELL
    if path.name in CONFIG_NAMES or path.suffix in {".toml", ".yaml", ".yml", ".json"}:
        return FileCategory.CONFIG
    if path.suffix.lower() in {".md", ".rst", ".txt"}:
        return FileCategory.DOCS
    return FileCategory.OTHER


def is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & (os.X_OK))


def risk_tags(path: Path, relative: str, category: FileCategory) -> tuple[str, ...]:
    tags: list[str] = []
    if category in {FileCategory.PYTHON, FileCategory.TEST}:
        tags.append("python-runtime")
    if category == FileCategory.SHELL:
        tags.extend(["process-exec", "quoting"])
    if category == FileCategory.NOTIFIER:
        tags.extend(["process-exec", "secrets", "network"])
    if category == FileCategory.CI:
        tags.extend(["supply-chain", "ci"])
    if category == FileCategory.CONFIG:
        tags.append("configuration")
    if "cli" in path.stem or relative.startswith("scripts/"):
        tags.append("cli-contract")
    if "core" in path.stem or "models" in path.stem:
        tags.extend(["data-contract", "file-safety"])
    return tuple(dict.fromkeys(tags))
