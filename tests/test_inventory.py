import subprocess
from pathlib import Path

import pytest

from review_gauntlet.inventory import (
    build_inventory,
    build_inventory_for_paths,
    matches_review_excluded_package_file_name_pattern,
    matches_review_excluded_package_relative_path_pattern,
    should_include_review_relative_path,
)
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


def test_build_inventory_excludes_ocr_inspired_artifact_directories(tmp_path: Path) -> None:
    included_files = ["src/pkg/core.py", "frontend/app.ts"]
    excluded_files = [
        "vendor/lib.go",
        "node_modules/pkg/index.js",
        "target/debug/app",
        ".happypack/cache.json",
        ".cachefile/state.json",
        "_packages/pkg.tgz",
        "rpm/build.spec",
        "pkgs/archive.tar",
        "oh_modules/generated.ets",
    ]
    for relative in [*included_files, *excluded_files]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content\n", encoding="utf-8")

    inventory_paths = {file.path for file in build_inventory(tmp_path).files}

    assert set(included_files) <= inventory_paths
    assert not (set(excluded_files) & inventory_paths)


def test_review_path_filter_excludes_default_review_noise() -> None:
    eligible = ["src/app.py", "frontend/app.ts", "lib/foo.rb"]
    excluded = [
        "openspec/specs/review-sessions/spec.md",
        "tests/test_core.py",
        "docs/usage.md",
        "foo_test.go",
        "foo_test.rs",
        "FooTest.java",
        "FooTests.kt",
        "app.spec.ts",
        "app.test.tsx",
        "test_core.py",
        "spec/foo_spec.rb",
        "frontend/__tests__/app.ts",
        "oh_modules/generated.ets",
        "component.spec.ets",
    ]

    assert all(should_include_review_relative_path(path) for path in eligible)
    assert not any(should_include_review_relative_path(path) for path in excluded)


PACKAGE_REVIEW_EXCLUDED_PATHS = [
    "uv.lock",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "services/api/requirements-prod.txt",
    "constraints.txt",
    "constraints-ci.txt",
    "services/api/constraints-prod.txt",
    "environment.yml",
    "environment.yaml",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    "deno.json",
    "deno.jsonc",
    "deno.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "go.work",
    "go.work.sum",
    "pom.xml",
    "gradle.lockfile",
    "gradle/libs.versions.toml",
    "services/api/gradle/libs.versions.toml",
    "Gemfile",
    "Gemfile.lock",
    "example.gemspec",
    "composer.json",
    "composer.lock",
    "Package.swift",
    "Package.resolved",
    "pubspec.yaml",
    "pubspec.lock",
    "mix.lock",
    "rebar.lock",
    "vcpkg.json",
    "vcpkg-lock.json",
    "conanfile.txt",
    "flake.lock",
    "cabal.project.freeze",
    "stack.yaml.lock",
    "package.yaml",
    "Manifest.toml",
    "renv.lock",
]


@pytest.mark.parametrize("relative_path", PACKAGE_REVIEW_EXCLUDED_PATHS)
def test_review_path_filter_excludes_package_files(relative_path: str) -> None:
    assert not should_include_review_relative_path(relative_path)


@pytest.mark.parametrize(
    "file_name",
    ["requirements-dev.txt", "constraints-ci.txt", "example.gemspec"],
)
def test_package_file_name_patterns_match_basename_only(file_name: str) -> None:
    assert matches_review_excluded_package_file_name_pattern(file_name)


@pytest.mark.parametrize(
    "relative_path",
    ["gradle/libs.versions.toml", "services/api/gradle/libs.versions.toml"],
)
def test_package_relative_path_patterns_match_nested_gradle_versions(
    relative_path: str,
) -> None:
    assert matches_review_excluded_package_relative_path_pattern(relative_path)


def test_package_files_remain_in_general_inventory(tmp_path: Path) -> None:
    package_files = ["uv.lock", "package.json", "Cargo.lock"]
    for relative in ["src/app.py", *package_files]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content\n", encoding="utf-8")

    inventory_paths = {file.path for file in build_inventory(tmp_path).files}

    assert set(package_files) <= inventory_paths
    assert "src/app.py" in inventory_paths


def test_target_scoped_inventory_skips_unsafe_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    outside = tmp_path.parent / "outside-review-gauntlet.py"
    outside.write_text("print('escape')\n", encoding="utf-8")

    inventory = build_inventory_for_paths(
        tmp_path,
        ("src/app.py", "../outside-review-gauntlet.py", str(outside)),
    )

    assert [file.path for file in inventory.files] == ["src/app.py"]


@pytest.mark.parametrize(
    "relative_path",
    ["setup.py", "build.gradle", "build.gradle.kts", "mix.exs", "conanfile.py", "build.zig"],
)
def test_review_path_filter_keeps_package_adjacent_executable_logic(
    relative_path: str,
) -> None:
    assert should_include_review_relative_path(relative_path)


def test_git_inventory_excludes_review_gauntlet_state(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / ".gitignore").write_text("ignored.log\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    for relative in ("vendor/lib.go", "node_modules/pkg/index.js", "target/debug/app"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".review-gauntlet" / "runs").mkdir(parents=True)
    (tmp_path / ".review-gauntlet" / "runs" / "prompt.md").write_text(
        "generated\n", encoding="utf-8"
    )
    (tmp_path / "ignored.log").write_text("ignored\n", encoding="utf-8")
    subprocess.run(
        [
            "git",
            "add",
            ".gitignore",
            "src/app.py",
            "vendor/lib.go",
            "node_modules/pkg/index.js",
            "target/debug/app",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    inventory = build_inventory(tmp_path)
    inventory_paths = {file.path for file in inventory.files}

    assert "src/app.py" in inventory_paths
    assert ".gitignore" in inventory_paths
    assert "vendor/lib.go" not in inventory_paths
    assert "node_modules/pkg/index.js" not in inventory_paths
    assert "target/debug/app" not in inventory_paths
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
