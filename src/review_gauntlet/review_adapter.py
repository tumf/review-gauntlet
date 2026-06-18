from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import IO, NoReturn, Protocol, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from review_gauntlet.config import TEMPLATE_PATTERN, CommandAdapterConfig, OutputMode
from review_gauntlet.ocr_rules import OCRComment, RuleDocument, Ruleset
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.subprocess_failures import subprocess_startup_failure_details

RAW_SNIPPET_LIMIT = 500
VERDICT_OUTPUT_SIZE_LIMIT_BYTES = 1_000_000
STRICT_JSON_HINT = (
    "External adapters must write strict JSON with double-quoted strings and no markdown fences."
)


class ReviewAdapterError(RuntimeError):
    def __init__(self, message: str, *, failure: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.failure = failure or {"error": message}


class _QuietTimeoutExpired(Exception):
    def __init__(self, timeout: float, stdout: str, stderr: str) -> None:
        super().__init__(f"no output for {timeout:.1f}s")
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr


class ReviewAdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cell_id: str
    comments: tuple[OCRComment, ...] = ()


class ReviewAdapter(Protocol):
    def review(self, cell: ReviewCell) -> ReviewAdapterResult: ...


class CancellableReviewAdapter(ReviewAdapter, Protocol):
    def cancel(self) -> None: ...


def cancel_adapter(adapter: ReviewAdapter) -> None:
    cancel = getattr(adapter, "cancel", None)
    if callable(cancel):
        cancel()


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


def validate_verdict_json(verdict_text: str) -> VerdictPayload:
    return VerdictPayload.model_validate_json(verdict_text)


class FileMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file_size_bytes: int
    line_count: int


class PromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_root: str
    cell: ReviewCell
    rule: RuleDocument
    ruleset_digest: str
    file_metadata: FileMetadata
    output_mode: OutputMode = OutputMode.STDOUT_JSON
    verdict_output_file: str | None = None
    review_commit: str | None = None


def build_review_prompt(context: PromptContext) -> str:
    commit_lines = _review_commit_prompt_lines(context)
    contract = {
        "comments": [
            {
                "path": context.cell.file_path,
                "content": "Issue description for this exact review cell path only",
                "suggestion_code": "Suggested code",
                "existing_code": "Existing code",
                "start_line": 1,
                "end_line": 1,
                "thinking": "Optional reasoning",
            }
        ]
    }
    output_instructions = _prompt_output_instructions(context)
    return "\n".join(
        [
            "# review-gauntlet OCR Review Prompt",
            "",
            "You are an external code review CLI. Produce verdict JSON matching the contract.",
            "Do not include provider credentials or markdown fences in the verdict JSON.",
            "",
            "## Output Contract",
            *output_instructions,
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
            *commit_lines,
            f"file_size_bytes: {context.file_metadata.file_size_bytes}",
            f"line_count: {context.file_metadata.line_count}",
            "",
            "Source file contents are not embedded in this prompt. When source inspection is "
            "needed, read the target file from repository_root plus file_path unless "
            "review_commit is provided.",
            "",
            "## Review Scope Guardrails",
            "Only report issues whose JSON path exactly equals the Review Cell file_path above.",
            "You may inspect related files to understand context, but do not emit comments for "
            "related files or helper files.",
            "If the only issue you find is in a different file, return an empty comments array.",
            "A verdict comment whose path differs from file_path will be rejected by the adapter.",
            "",
            "## Selected Rule",
            f"rule_document: {context.rule.filename}",
            context.rule.content,
            "",
            "## Verdict JSON Contract",
            "The verdict object must contain exactly one top-level key: comments.",
            "Each comment object may contain only these keys: path, content, suggestion_code, "
            "existing_code, start_line, end_line, thinking.",
            "Do not include rule_id, cell_id, severity, confidence, title, category, metadata, "
            "or any other keys.",
            f"Every comment.path MUST equal: {context.cell.file_path}",
            json.dumps(contract, indent=2, sort_keys=True),
            "",
        ]
    )


def _review_commit_prompt_lines(context: PromptContext) -> list[str]:
    if context.review_commit is None:
        return []
    return [
        f"review_commit: {context.review_commit}",
        "Read this file as it exists at commit "
        f"{context.review_commit}: git show {context.review_commit}:{context.cell.file_path}",
    ]


def _prompt_output_instructions(context: PromptContext) -> list[str]:
    if context.output_mode == OutputMode.FILE_JSON:
        if context.verdict_output_file is None:
            raise ValueError("file-json prompt requires verdict_output_file")
        return [
            "Write the final verdict JSON to this file:",
            context.verdict_output_file,
            "Before finishing, validate the file with:",
            f"review-gauntlet validate-verdict {context.verdict_output_file} "
            f"--expected-path {context.cell.file_path}",
            "If validation fails, fix the JSON file and run the validator again.",
            "Stdout and stderr are audit/progress channels only; they are preserved but not "
            "parsed as verdict input.",
            "Do not rely on stdout or stderr to deliver the verdict when file-json output "
            "is active.",
        ]
    return [
        "Write exactly one verdict JSON object to stdout.",
        "Do not write progress text, markdown, or any non-JSON text to stdout.",
    ]


class CommandReviewAdapter:
    def __init__(
        self,
        *,
        config: CommandAdapterConfig,
        root: Path,
        state_dir: Path,
        run_id: int,
        ruleset: Ruleset,
        review_commit: str | None = None,
    ) -> None:
        self._config = config
        self._root = root.resolve()
        self._state_dir = state_dir.resolve()
        self._run_id = str(run_id)
        self._run_dir = (self._state_dir / "runs" / self._run_id).resolve()
        self._ruleset = ruleset
        self._review_commit = review_commit
        self._process_lock = threading.Lock()
        self._active_processes: set[subprocess.Popen[str]] = set()

    @property
    def timeout_seconds(self) -> float:
        return self._config.timeout_seconds

    def cancel(self) -> None:
        with self._process_lock:
            processes = tuple(self._active_processes)
        for process in processes:
            try:
                if process.poll() is None:
                    process.terminate()
            except OSError:
                pass

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        cells_dir = (self._run_dir / "cells").resolve()
        cell_dir = (cells_dir / cell.id).resolve()
        try:
            cell_dir.relative_to(cells_dir)
        except ValueError as exc:
            raise ReviewAdapterError(f"unsafe review cell id for artifacts: {cell.id}") from exc
        cell_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = cell_dir / "prompt.md"
        output_file = cell_dir / "verdict.json"
        stdout_file = cell_dir / "stdout.txt"
        stderr_file = cell_dir / "stderr.txt"
        failure_file = cell_dir / "failure.json"
        initial_variables = self._variables(cell, cell_dir, output_file, "")
        output_path = self._resolve_output_path(initial_variables, cell_dir)
        file_metadata = self._read_cell_file_metadata(cell)
        prompt = build_review_prompt(
            PromptContext(
                repository_root=str(self._root),
                cell=cell,
                rule=self._ruleset.select_rule_doc(cell.file_path),
                ruleset_digest=self._ruleset.digest,
                file_metadata=file_metadata,
                output_mode=self._config.output.mode,
                verdict_output_file=str(output_path),
                review_commit=self._review_commit,
            )
        )
        prompt_file.write_text(prompt, encoding="utf-8")
        variables = self._variables(cell, cell_dir, output_path, prompt)
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
            "cwd": None if cwd is None else str(cwd),
            "cwd_mode": "inherited" if cwd is None else "explicit",
            "env_overrides": sorted(self._config.env),
            "output_mode": self._config.output.mode,
            "output_path": str(output_path),
            "prompt_artifact": str(prompt_file),
            "timeout_seconds": self._config.timeout_seconds,
            "quiet_timeout_seconds": self._config.quiet_timeout_seconds,
        }
        (cell_dir / "command.json").write_text(
            json.dumps(command_metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        if self._config.output.mode == OutputMode.FILE_JSON:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        completed = self._run_command(
            argv=argv,
            cwd=cwd,
            env=env,
            stdout_file=stdout_file,
            stderr_file=stderr_file,
            failure_file=failure_file,
        )
        if completed.returncode != 0:
            self._fail(
                f"command exited with status {completed.returncode}",
                failure_file,
                {"argv": argv, "returncode": completed.returncode},
            )
        if self._config.output.mode == OutputMode.STDOUT_JSON:
            stdout_size = len(completed.stdout.encode("utf-8"))
            if stdout_size > VERDICT_OUTPUT_SIZE_LIMIT_BYTES:
                self._fail(
                    f"stdout verdict exceeds {VERDICT_OUTPUT_SIZE_LIMIT_BYTES} bytes",
                    failure_file,
                    {
                        "output_size_bytes": stdout_size,
                        "size_limit_bytes": VERDICT_OUTPUT_SIZE_LIMIT_BYTES,
                    },
                )
            verdict_text = completed.stdout
        else:
            verdict_text = self._read_output_file(output_path, failure_file)
        raw_verdict_file = cell_dir / "verdict.raw.json"
        raw_verdict_file.write_text(verdict_text, encoding="utf-8")
        try:
            payload = validate_verdict_json(verdict_text)
        except (ValueError, ValidationError) as exc:
            self._fail(
                "invalid verdict JSON",
                failure_file,
                _invalid_verdict_failure_details(
                    error=exc,
                    output_mode=self._config.output.mode,
                    verdict_path=output_path,
                    raw_verdict_path=raw_verdict_file,
                    verdict_text=verdict_text,
                ),
            )
        comments = self._validated_comments_for_cell(
            payload.comments, cell, file_metadata.line_count, failure_file
        )
        output_file.write_text(
            VerdictPayload(comments=comments).model_dump_json(indent=2), encoding="utf-8"
        )
        return ReviewAdapterResult(cell_id=cell.id, comments=comments)

    def _run_command(
        self,
        *,
        argv: list[str],
        cwd: Path | None,
        env: dict[str, str],
        stdout_file: Path,
        stderr_file: Path,
        failure_file: Path,
    ) -> subprocess.CompletedProcess[str]:
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
        except FileNotFoundError as exc:
            self._fail(
                f"command not found: {argv[0]}", failure_file, {"argv": argv, "error": str(exc)}
            )
        except OSError as exc:
            self._fail(
                "command startup failed",
                failure_file,
                subprocess_startup_failure_details(argv, exc),
            )
        with self._process_lock:
            self._active_processes.add(process)
        try:
            try:
                stdout, stderr = self._communicate(process)
            except subprocess.TimeoutExpired as exc:
                stdout_file.write_text(_process_output_text(exc.stdout), encoding="utf-8")
                stderr_file.write_text(_process_output_text(exc.stderr), encoding="utf-8")
                self._fail(
                    f"command timed out after {self._config.timeout_seconds} seconds",
                    failure_file,
                    {"argv": argv, "timeout_seconds": self._config.timeout_seconds},
                )
            except _QuietTimeoutExpired as exc:
                stdout_file.write_text(_process_output_text(exc.stdout), encoding="utf-8")
                stderr_file.write_text(_process_output_text(exc.stderr), encoding="utf-8")
                self._fail(
                    f"command produced no output for {self._config.quiet_timeout_seconds}s",
                    failure_file,
                    {"argv": argv, "quiet_timeout_seconds": self._config.quiet_timeout_seconds},
                )
            except Exception as exc:
                stdout_file.write_text("", encoding="utf-8")
                stderr_file.write_text("", encoding="utf-8")
                self._fail(
                    f"unexpected error communicating with command: {exc}",
                    failure_file,
                    {"argv": argv, "error": str(exc), "error_type": type(exc).__name__},
                )
            stdout_file.write_text(_process_output_text(stdout), encoding="utf-8")
            stderr_file.write_text(_process_output_text(stderr), encoding="utf-8")
            if process.returncode is not None and process.returncode < 0:
                self._fail(
                    "command cancelled",
                    failure_file,
                    {"argv": argv, "returncode": process.returncode, "cancelled": True},
                )
            if process.returncode is None:
                raise ReviewAdapterError("returncode unset after communicate()")
            return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
        finally:
            with self._process_lock:
                self._active_processes.discard(process)
            if process.poll() is None:
                with contextlib.suppress(OSError):
                    process.kill()

    def _communicate(self, process: subprocess.Popen[str]) -> tuple[str, str]:
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        last_activity = [time.monotonic()]
        activity_lock = threading.Lock()

        def _read(pipe: IO[str], buf: list[str]) -> None:
            for chunk in iter(lambda: pipe.read(4096), ""):
                with activity_lock:
                    last_activity[0] = time.monotonic()
                buf.append(chunk)

        threads = [
            threading.Thread(target=_read, args=(process.stdout, stdout_chunks), daemon=True),
            threading.Thread(target=_read, args=(process.stderr, stderr_chunks), daemon=True),
        ]
        for t in threads:
            t.start()

        start = time.monotonic()
        timeout_exc: subprocess.TimeoutExpired | _QuietTimeoutExpired | None = None
        while any(t.is_alive() for t in threads):
            alive = next((t for t in threads if t.is_alive()), None)
            if alive:
                alive.join(timeout=0.05)
            now = time.monotonic()
            if now - start >= self._config.timeout_seconds:
                timeout_exc = subprocess.TimeoutExpired(process.args, self._config.timeout_seconds)
                break
            with activity_lock:
                idle = now - last_activity[0]
            if idle >= self._config.quiet_timeout_seconds:
                timeout_exc = _QuietTimeoutExpired(self._config.quiet_timeout_seconds, "", "")
                break

        if timeout_exc is not None:
            process.terminate()
            for t in threads:
                t.join(timeout=2)
            if process.poll() is None:
                with contextlib.suppress(OSError):
                    process.kill()
            for t in threads:
                t.join(timeout=1)
            stdout = "".join(stdout_chunks)
            stderr = "".join(stderr_chunks)
            if isinstance(timeout_exc, _QuietTimeoutExpired):
                raise _QuietTimeoutExpired(self._config.quiet_timeout_seconds, stdout, stderr)
            raise subprocess.TimeoutExpired(
                process.args, self._config.timeout_seconds, stdout, stderr
            )

        for t in threads:
            t.join()
        process.wait()
        return "".join(stdout_chunks), "".join(stderr_chunks)

    def _read_cell_file_metadata(self, cell: ReviewCell) -> FileMetadata:
        file_path = (self._root / cell.file_path).resolve()
        try:
            file_path.relative_to(self._root)
        except ValueError as exc:
            raise ReviewAdapterError(
                f"unsafe review cell path outside repository: {cell.file_path}"
            ) from exc
        if self._review_commit is not None:
            try:
                result = subprocess.run(
                    ["git", "show", f"{self._review_commit}:{cell.file_path}"],
                    cwd=self._root,
                    capture_output=True,
                    timeout=10,
                    check=True,
                )
                content = result.stdout
            except subprocess.TimeoutExpired as exc:
                raise ReviewAdapterError(
                    f"git show timed out reading {cell.file_path} at commit {self._review_commit}"
                ) from exc
            except subprocess.CalledProcessError as exc:
                raise ReviewAdapterError(
                    f"cannot read review cell path at commit {self._review_commit}: "
                    f"{cell.file_path}"
                ) from exc
        else:
            if not file_path.is_file():
                raise ReviewAdapterError(f"review cell path is not a file: {cell.file_path}")
            content = file_path.read_bytes()
        return FileMetadata(
            file_size_bytes=len(content),
            line_count=content.count(b"\n") + (0 if content.endswith(b"\n") or not content else 1),
        )

    def _variables(
        self, cell: ReviewCell, cell_dir: Path, output_file: Path, prompt: str
    ) -> dict[str, str]:
        return {
            "repo_root": str(self._root),
            "state_dir": str(self._state_dir),
            "run_id": self._run_id,
            "run_dir": str(self._run_dir),
            "cell_id": cell.id,
            "cell_dir": str(cell_dir),
            "prompt": prompt,
            "output_file": str(output_file),
            "file_path": cell.file_path,
            "rule_id": cell.rule_id,
        }

    def _expand_all(self, values: tuple[str, ...], variables: dict[str, str]) -> list[str]:
        return [self._expand(value, variables) for value in values]

    def _expand(self, value: str, variables: dict[str, str]) -> str:
        placeholder = "\x00REVIEW_GAUNTLET_LITERAL_BRACE\x00"
        protected = value.replace("{{", placeholder + "OPEN").replace("}}", placeholder + "CLOSE")

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            try:
                return variables[name]
            except KeyError as exc:
                raise ReviewAdapterError(f"unknown template variable: {name}") from exc

        expanded = TEMPLATE_PATTERN.sub(replace, protected)
        return expanded.replace(placeholder + "OPEN", "{").replace(placeholder + "CLOSE", "}")

    def _resolve_cwd(self, variables: dict[str, str]) -> Path | None:
        if self._config.cwd is None:
            return None
        cwd = Path(self._expand(self._config.cwd, variables))
        resolved = (self._root / cwd).resolve() if not cwd.is_absolute() else cwd.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise ReviewAdapterError(
                f"adapter.cwd must stay inside repository root: {resolved}"
            ) from exc
        if not resolved.is_dir():
            raise ReviewAdapterError(f"adapter.cwd is not a directory: {resolved}")
        return resolved

    def _resolve_output_path(self, variables: dict[str, str], cell_dir: Path) -> Path:
        if self._config.output.mode == OutputMode.STDOUT_JSON:
            return cell_dir / "verdict.json"
        raw = self._config.output.path or variables["output_file"]
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
        try:
            output_size = output_path.stat().st_size
        except OSError as exc:
            self._fail(
                f"cannot stat verdict output file: {exc}",
                failure_file,
                {"output_path": str(output_path), "error": str(exc)},
            )
        if output_size > VERDICT_OUTPUT_SIZE_LIMIT_BYTES:
            self._fail(
                "verdict output file exceeds "
                f"{VERDICT_OUTPUT_SIZE_LIMIT_BYTES} bytes: {output_path}",
                failure_file,
                {
                    "output_path": str(output_path),
                    "output_size_bytes": output_size,
                    "size_limit_bytes": VERDICT_OUTPUT_SIZE_LIMIT_BYTES,
                },
            )
        try:
            content = output_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._fail(
                f"cannot read verdict output file: {exc}",
                failure_file,
                {"output_path": str(output_path), "error": str(exc)},
            )
        return content

    def _fail(self, message: str, failure_file: Path, details: dict[str, object]) -> NoReturn:
        payload = {"error": message, **details}
        failure_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        raise ReviewAdapterError(message, failure=payload)

    def _validated_comments_for_cell(
        self,
        comments: tuple[OCRComment, ...],
        cell: ReviewCell,
        line_count: int,
        failure_file: Path,
    ) -> tuple[OCRComment, ...]:
        accepted: list[OCRComment] = []
        for index, comment in enumerate(comments):
            if comment.path != cell.file_path:
                self._fail(
                    "verdict comment targets a different review cell path",
                    failure_file,
                    {
                        "comment_index": index,
                        "comment_path": comment.path,
                        "cell_path": cell.file_path,
                    },
                )
            if comment.imprecise:
                accepted.append(comment)
                continue
            if comment.start_line < 1 or comment.end_line < comment.start_line:
                self._fail(
                    "verdict comment has an invalid line range",
                    failure_file,
                    {
                        "comment_index": index,
                        "comment_path": comment.path,
                        "start_line": comment.start_line,
                        "end_line": comment.end_line,
                        "line_count": line_count,
                    },
                )
            if comment.end_line > line_count:
                self._fail(
                    "verdict comment line range exceeds review cell line count",
                    failure_file,
                    {
                        "comment_index": index,
                        "comment_path": comment.path,
                        "start_line": comment.start_line,
                        "end_line": comment.end_line,
                        "line_count": line_count,
                    },
                )
            accepted.append(comment)
        return tuple(accepted)


def _invalid_verdict_failure_details(
    *,
    error: ValueError | ValidationError,
    output_mode: OutputMode,
    verdict_path: Path,
    raw_verdict_path: Path,
    verdict_text: str,
) -> dict[str, object]:
    return {
        "error": str(error),
        "output_mode": output_mode,
        "verdict_path": str(verdict_path),
        "raw_verdict_path": str(raw_verdict_path),
        "raw_snippet": _raw_snippet(verdict_text, _json_error_position(error)),
        "hint": STRICT_JSON_HINT,
    }


def _json_error_position(error: ValueError | ValidationError) -> int | None:
    if isinstance(error, json.JSONDecodeError):
        return error.pos
    if isinstance(error, ValidationError):
        for item in error.errors():
            if item.get("type") != "json_invalid":
                continue
            ctx = item.get("ctx")
            if not isinstance(ctx, dict):
                continue
            raw_error = ctx.get("error")
            if isinstance(raw_error, str):
                raw_input = item.get("input")
                position = _line_column_position(
                    raw_input if isinstance(raw_input, str) else "", raw_error
                )
                if position is not None:
                    return position
    return None


def _line_column_position(value: str, message: str) -> int | None:
    match = re.search(r"line (\d+) column (\d+)", message)
    if match is None:
        return None
    line = int(match.group(1))
    column = int(match.group(2))
    if line < 1 or column < 1:
        return None
    lines = value.splitlines(keepends=True)
    if line > len(lines):
        return None
    return sum(len(part) for part in lines[: line - 1]) + column - 1


def _raw_snippet(value: str, position: int | None, *, limit: int = RAW_SNIPPET_LIMIT) -> str:
    if len(value) <= limit:
        return value
    if position is None:
        return value[:limit] + "…"
    half_limit = limit // 2
    start = max(position - half_limit, 0)
    end = min(start + limit, len(value))
    start = max(end - limit, 0)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(value) else ""
    return f"{prefix}{value[start:end]}{suffix}"


def _process_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
