from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import NoReturn, Protocol, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from review_gauntlet.config import CommandAdapterConfig, InputMode, OutputMode
from review_gauntlet.ocr_rules import OCRComment, RuleDocument, Ruleset
from review_gauntlet.review_cells import ReviewCell

TEMPLATE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ReviewAdapterError(RuntimeError):
    def __init__(self, message: str, *, failure: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.failure = failure or {"error": message}


class ReviewAdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cell_id: str
    comments: tuple[OCRComment, ...] = ()


class ReviewAdapter(Protocol):
    def review(self, cell: ReviewCell) -> ReviewAdapterResult: ...


class FakeReviewAdapter:
    def __init__(self, fixtures_path: Path | None = None) -> None:
        self._fixtures = _load_fixtures(fixtures_path) if fixtures_path else {}

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        raw_comments = self._fixtures.get(cell.id) or self._fixtures.get(cell.file_path) or []
        comments = tuple(OCRComment.model_validate(comment) for comment in raw_comments)
        return ReviewAdapterResult(cell_id=cell.id, comments=comments)


def _load_fixtures(path: Path) -> dict[str, list[dict[str, object]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fake review fixture must be a JSON object")
    raw = cast(dict[str, object], data)
    result: dict[str, list[dict[str, object]]] = {}
    for key, value in raw.items():
        if not isinstance(value, list):
            raise ValueError("fake review fixture maps strings to comment lists")
        comments: list[dict[str, object]] = []
        for item in cast(list[object], value):
            if not isinstance(item, dict):
                raise ValueError("fake review fixture comments must be objects")
            comments.append(cast(dict[str, object], item))
        result[key] = comments
    return result


class VerdictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comments: tuple[OCRComment, ...] = ()


class PromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_root: str
    cell: ReviewCell
    rule: RuleDocument
    ruleset_digest: str
    file_content: str


def build_review_prompt(context: PromptContext) -> str:
    contract = {
        "comments": [
            {
                "path": context.cell.file_path,
                "content": "Issue description",
                "suggestion_code": "Suggested code",
                "existing_code": "Existing code",
                "start_line": 1,
                "end_line": 1,
                "thinking": "Optional reasoning",
            }
        ]
    }
    return "\n".join(
        [
            "# review-gauntlet OCR Review Prompt",
            "",
            "You are an external code review CLI. Return only verdict JSON matching the contract.",
            "Do not include provider credentials, markdown fences, or non-JSON text.",
            "",
            "## Repository Context",
            f"repository_root: {context.repository_root}",
            f"ruleset_digest: {context.ruleset_digest}",
            "",
            "## Review Cell",
            f"cell_id: {context.cell.id}",
            f"file_path: {context.cell.file_path}",
            f"slice_id: {context.cell.slice_id}",
            f"rule_id: {context.cell.rule_id}",
            f"content_digest: {context.cell.content_digest}",
            "",
            "## Selected Rule",
            f"rule_document: {context.rule.filename}",
            context.rule.content,
            "",
            "## Verdict JSON Contract",
            json.dumps(contract, indent=2, sort_keys=True),
            "",
            "## File Content",
            f"```text path={context.cell.file_path}",
            context.file_content,
            "```",
            "",
        ]
    )


class CommandReviewAdapter:
    def __init__(
        self,
        *,
        config: CommandAdapterConfig,
        root: Path,
        state_dir: Path,
        run_id: int,
        ruleset: Ruleset,
    ) -> None:
        self._config = config
        self._root = root.resolve()
        self._state_dir = state_dir.resolve()
        self._run_id = str(run_id)
        self._run_dir = (self._state_dir / "runs" / self._run_id).resolve()
        self._ruleset = ruleset

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        cell_dir = (self._run_dir / "cells" / cell.id).resolve()
        cell_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = cell_dir / "prompt.md"
        output_file = cell_dir / "verdict.json"
        stdout_file = cell_dir / "stdout.txt"
        stderr_file = cell_dir / "stderr.txt"
        failure_file = cell_dir / "failure.json"
        prompt = build_review_prompt(
            PromptContext(
                repository_root=str(self._root),
                cell=cell,
                rule=self._ruleset.select_rule_doc(cell.file_path),
                ruleset_digest=self._ruleset.digest,
                file_content=(self._root / cell.file_path).read_text(encoding="utf-8"),
            )
        )
        prompt_file.write_text(prompt, encoding="utf-8")
        variables = self._variables(cell, cell_dir, prompt_file, output_file)
        output_path = self._resolve_output_path(variables, cell_dir)
        argv = [
            self._expand(self._config.command, variables),
            *self._expand_all(self._config.args, variables),
        ]
        cwd = self._resolve_cwd(variables)
        env = os.environ.copy()
        env.update({key: self._expand(value, variables) for key, value in self._config.env.items()})
        command_metadata = {
            "argv": argv,
            "cwd": str(cwd),
            "input_mode": self._config.input.mode,
            "output_mode": self._config.output.mode,
            "timeout_seconds": self._config.timeout_seconds,
        }
        (cell_dir / "command.json").write_text(
            json.dumps(command_metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        stdin = prompt if self._config.input.mode == InputMode.STDIN else None
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                input=stdin,
                text=True,
                capture_output=True,
                timeout=self._config.timeout_seconds,
                shell=False,
                check=False,
            )
        except FileNotFoundError as exc:
            self._fail(
                f"command not found: {argv[0]}", failure_file, {"argv": argv, "error": str(exc)}
            )
        except subprocess.TimeoutExpired as exc:
            stdout_file.write_text(_process_output_text(exc.stdout), encoding="utf-8")
            stderr_file.write_text(_process_output_text(exc.stderr), encoding="utf-8")
            self._fail(
                f"command timed out after {self._config.timeout_seconds} seconds",
                failure_file,
                {"argv": argv, "timeout_seconds": self._config.timeout_seconds},
            )
        stdout_file.write_text(completed.stdout, encoding="utf-8")
        stderr_file.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            self._fail(
                f"command exited with status {completed.returncode}",
                failure_file,
                {"argv": argv, "returncode": completed.returncode},
            )
        verdict_text = (
            completed.stdout
            if self._config.output.mode == OutputMode.STDOUT_JSON
            else self._read_output_file(output_path, failure_file)
        )
        (cell_dir / "verdict.raw.json").write_text(verdict_text, encoding="utf-8")
        try:
            payload = VerdictPayload.model_validate_json(verdict_text)
        except (ValueError, ValidationError) as exc:
            self._fail(
                "invalid verdict JSON",
                failure_file,
                {"error": str(exc), "output_mode": self._config.output.mode},
            )
        output_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return ReviewAdapterResult(cell_id=cell.id, comments=payload.comments)

    def _variables(
        self, cell: ReviewCell, cell_dir: Path, prompt_file: Path, output_file: Path
    ) -> dict[str, str]:
        return {
            "repo_root": str(self._root),
            "state_dir": str(self._state_dir),
            "run_id": self._run_id,
            "run_dir": str(self._run_dir),
            "cell_id": cell.id,
            "cell_dir": str(cell_dir),
            "prompt_file": str(prompt_file),
            "output_file": str(output_file),
            "file_path": cell.file_path,
            "rule_id": cell.rule_id,
        }

    def _expand_all(self, values: tuple[str, ...], variables: dict[str, str]) -> list[str]:
        return [self._expand(value, variables) for value in values]

    def _expand(self, value: str, variables: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            try:
                return variables[name]
            except KeyError as exc:
                raise ReviewAdapterError(f"unknown template variable: {name}") from exc

        return TEMPLATE_PATTERN.sub(replace, value)

    def _resolve_cwd(self, variables: dict[str, str]) -> Path:
        if self._config.cwd is None:
            return self._root
        cwd = Path(self._expand(self._config.cwd, variables))
        return (self._root / cwd).resolve() if not cwd.is_absolute() else cwd.resolve()

    def _resolve_output_path(self, variables: dict[str, str], cell_dir: Path) -> Path:
        if self._config.output.mode == OutputMode.STDOUT_JSON:
            return cell_dir / "verdict.json"
        raw = self._config.output.path
        if raw is None:
            raise ReviewAdapterError("adapter.output.path is required")
        expanded = Path(self._expand(raw, variables))
        output_path = (
            (cell_dir / expanded).resolve() if not expanded.is_absolute() else expanded.resolve()
        )
        try:
            output_path.relative_to(cell_dir)
        except ValueError as exc:
            raise ReviewAdapterError(
                f"unsafe output path outside cell artifacts: {output_path}"
            ) from exc
        return output_path

    def _read_output_file(self, output_path: Path, failure_file: Path) -> str:
        if not output_path.is_file():
            self._fail(
                f"missing verdict output file: {output_path}",
                failure_file,
                {"output_path": str(output_path)},
            )
        return output_path.read_text(encoding="utf-8")

    def _fail(self, message: str, failure_file: Path, details: dict[str, object]) -> NoReturn:
        payload = {"error": message, **details}
        failure_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        raise ReviewAdapterError(message, failure=payload)


def _process_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
