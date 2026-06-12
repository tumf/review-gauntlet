from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path

from review_gauntlet.models import FileCategory, FileRecord, Inventory, display_root

ARTIFACT_EXCLUDED_DIR_NAMES = {
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
    "vendor",
    "node_modules",
    "target",
    ".happypack",
    ".cachefile",
    "_packages",
    "rpm",
    "pkgs",
    "oh_modules",
}
ARTIFACT_EXCLUDED_FILE_NAMES = {".coverage", ".DS_Store"}
ARTIFACT_EXCLUDED_DIR_SUFFIXES = {".egg-info"}
REVIEW_EXCLUDED_TOP_LEVEL_DIRS = {"openspec", "tests", "docs"}
REVIEW_EXCLUDED_PATH_PARTS = {"__tests__", "oh_modules"}
REVIEW_EXCLUDED_SUFFIXES = {
    "_test.go",
    "_test.rs",
    "Test.java",
    "Tests.java",
    "Test.kt",
    "Tests.kt",
    ".spec.ts",
    ".spec.tsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".test.js",
    "_test.py",
    "_spec.rb",
    ".spec.ets",
    ".test.ets",
}
REVIEW_EXCLUDED_PREFIXES = {"test_"}
REVIEW_EXCLUDED_PACKAGE_FILE_NAMES = {
    "bun.lock",
    "bun.lockb",
    "cabal.project.freeze",
    "Cargo.lock",
    "Cargo.toml",
    "composer.json",
    "composer.lock",
    "conanfile.txt",
    "constraints.txt",
    "deno.json",
    "deno.jsonc",
    "deno.lock",
    "environment.yaml",
    "environment.yml",
    "flake.lock",
    "Gemfile",
    "Gemfile.lock",
    "go.mod",
    "go.sum",
    "go.work",
    "go.work.sum",
    "gradle.lockfile",
    "Manifest.toml",
    "mix.lock",
    "npm-shrinkwrap.json",
    "package-lock.json",
    "package.json",
    "Package.resolved",
    "Package.swift",
    "package.yaml",
    "Pipfile",
    "Pipfile.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pom.xml",
    "pubspec.lock",
    "pubspec.yaml",
    "rebar.lock",
    "renv.lock",
    "requirements.txt",
    "stack.yaml.lock",
    "uv.lock",
    "vcpkg-lock.json",
    "vcpkg.json",
    "yarn.lock",
}
REVIEW_EXCLUDED_PACKAGE_FILE_NAME_PATTERNS = {
    "*.gemspec",
    "constraints-*.txt",
    "requirements-*.txt",
}
REVIEW_EXCLUDED_PACKAGE_RELATIVE_PATH_PATTERNS = {
    "gradle/libs.versions.toml",
    "*/gradle/libs.versions.toml",
}
EXCLUDED_DIR_NAMES = ARTIFACT_EXCLUDED_DIR_NAMES
EXCLUDED_FILE_NAMES = ARTIFACT_EXCLUDED_FILE_NAMES
EXCLUDED_DIR_SUFFIXES = ARTIFACT_EXCLUDED_DIR_SUFFIXES
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
        if should_include_artifact_relative_path(relative) and (repo_root / relative).is_file()
    )
    return Inventory(root=display_root(repo_root), files=files)


def list_project_files(root: Path) -> list[Path]:
    tracked = git_file_list(root)
    if tracked is not None:
        return sorted(
            root / path for path in tracked if should_include_artifact_relative_path(path)
        )
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


def should_include_artifact_relative_path(relative: str | Path) -> bool:
    path = Path(relative)
    return not any(
        part in ARTIFACT_EXCLUDED_DIR_NAMES
        or part in ARTIFACT_EXCLUDED_FILE_NAMES
        or any(part.endswith(suffix) for suffix in ARTIFACT_EXCLUDED_DIR_SUFFIXES)
        for part in path.parts
    )


def should_include_relative_path(relative: str | Path) -> bool:
    return should_include_artifact_relative_path(relative)


def should_include_review_relative_path(relative: str | Path) -> bool:
    path = Path(relative)
    parts = path.parts
    if not should_include_artifact_relative_path(path):
        return False
    if parts and parts[0] in REVIEW_EXCLUDED_TOP_LEVEL_DIRS:
        return False
    if any(part in REVIEW_EXCLUDED_PATH_PARTS for part in parts):
        return False
    if is_review_excluded_package_file(path):
        return False
    name = path.name
    if name.startswith(tuple(REVIEW_EXCLUDED_PREFIXES)):
        return False
    return not name.endswith(tuple(REVIEW_EXCLUDED_SUFFIXES))


def is_review_excluded_package_file(path: Path) -> bool:
    relative = path.as_posix()
    return (
        path.name in REVIEW_EXCLUDED_PACKAGE_FILE_NAMES
        or any(
            fnmatch.fnmatchcase(path.name, pattern)
            for pattern in REVIEW_EXCLUDED_PACKAGE_FILE_NAME_PATTERNS
        )
        or any(
            fnmatch.fnmatchcase(relative, pattern)
            for pattern in REVIEW_EXCLUDED_PACKAGE_RELATIVE_PATH_PATTERNS
        )
    )


def should_include_path(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    return should_include_artifact_relative_path(path.relative_to(root))


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
