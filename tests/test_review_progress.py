import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import review_gauntlet.cli as cli
from review_gauntlet.cli import ReviewProgressReporter, main, review_cells_concurrently
from review_gauntlet.review_adapter import ReviewAdapterResult
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


def _init_review_repo(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(root), "--all", "--format", "json"])
    capsys.readouterr()


def _test_cell(cell_id: str) -> ReviewCell:
    return ReviewCell(
        id=cell_id,
        file_path="README.md",
        rule_id="docs",
        slice_id="docs",
        content_digest="digest",
    )


class InterruptingAdapter:
    def __init__(self) -> None:
        self.cancelled = False

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        if cell.id == "RGC-interrupt":
            raise KeyboardInterrupt
        return ReviewAdapterResult(cell_id=cell.id)

    def cancel(self) -> None:
        self.cancelled = True


def test_review_keyboard_interrupt_cancels_adapter_and_pending_cells(
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter = InterruptingAdapter()

    with pytest.raises(KeyboardInterrupt):
        review_cells_concurrently(
            adapter,
            [_test_cell("RGC-interrupt"), _test_cell("RGC-pending")],
            concurrency=1,
            reporter=ReviewProgressReporter(enabled=True),
        )

    captured = capsys.readouterr()
    assert adapter.cancelled is True
    assert "review cell cancelled: cell_id=RGC-pending" in captured.err


class ControlledFuture:
    def __init__(self, result: ReviewAdapterResult | None, *, done: bool) -> None:
        self._result = result
        self._done = done
        self.cancelled = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> bool:
        self.cancelled = True
        return True

    def result(self) -> ReviewAdapterResult:
        if self._result is None:
            raise AssertionError("pending future result must not be awaited during interrupt drain")
        return self._result


class ControlledExecutor:
    def __init__(self, futures: list[ControlledFuture]) -> None:
        self._futures = futures
        self.submitted = 0
        self.shutdown_wait: bool | None = None
        self.shutdown_cancel_futures: bool | None = None

    def submit(self, fn: object, cell: ReviewCell) -> ControlledFuture:
        del fn, cell
        future = self._futures[self.submitted]
        self.submitted += 1
        return future

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        self.shutdown_wait = wait
        self.shutdown_cancel_futures = cancel_futures


class CancellableAdapter:
    def __init__(self) -> None:
        self.cancelled = False

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        return ReviewAdapterResult(cell_id=cell.id)

    def cancel(self) -> None:
        self.cancelled = True


def test_review_interrupt_drains_completed_futures_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = ControlledFuture(ReviewAdapterResult(cell_id="RGC-complete"), done=True)
    pending = ControlledFuture(None, done=False)
    executor = ControlledExecutor([completed, pending])
    adapter = CancellableAdapter()
    observed: list[str] = []

    def fake_executor(*args: object, **kwargs: object) -> ControlledExecutor:
        del args, kwargs
        return executor

    def interrupted_as_completed(futures: object) -> Iterator[Any]:
        del futures
        raise KeyboardInterrupt
        yield

    monkeypatch.setattr(cli, "ThreadPoolExecutor", fake_executor)
    monkeypatch.setattr(cli, "as_completed", interrupted_as_completed)

    with pytest.raises(KeyboardInterrupt):
        review_cells_concurrently(
            adapter,
            [_test_cell("RGC-complete"), _test_cell("RGC-pending")],
            concurrency=2,
            on_result=lambda cell, outcome: observed.append(cell.id),
        )

    assert observed == ["RGC-complete"]
    assert adapter.cancelled is True
    assert pending.cancelled is True
    assert executor.shutdown_wait is False
    assert executor.shutdown_cancel_futures is True


def test_review_human_progress_goes_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_review_repo(tmp_path, capsys)
    fixture = tmp_path / ".review-gauntlet" / "fixtures" / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}", encoding="utf-8")

    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["reviewed_cells"] == 1
    assert "review progress:" in captured.err
    assert "selected_cells=1" in captured.err
    assert "adapter=FakeReviewAdapter" in captured.err
    assert "review cell start:" in captured.err
    assert "review cell success:" in captured.err


def test_review_json_stdout_is_clean_when_progress_enabled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_review_repo(tmp_path, capsys)
    fixture = tmp_path / ".review-gauntlet" / "fixtures" / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}", encoding="utf-8")

    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])

    captured = capsys.readouterr()
    assert "review progress:" not in captured.out
    assert json.loads(captured.out)["reviewed_cells"] == 1
    assert "review progress:" in captured.err


def test_review_agent_audience_suppresses_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_review_repo(tmp_path, capsys)
    fixture = tmp_path / ".review-gauntlet" / "fixtures" / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}", encoding="utf-8")

    main(
        [
            "review",
            str(tmp_path),
            "--fixture",
            str(fixture),
            "--budget",
            "1",
            "--format",
            "json",
            "--audience",
            "agent",
        ]
    )

    captured = capsys.readouterr()
    assert json.loads(captured.out)["reviewed_cells"] == 1
    assert captured.err == ""


def test_review_failure_progress_and_unreviewed_cell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_review_repo(tmp_path, capsys)
    config = tmp_path / "review-gauntlet.json"
    config.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": sys.executable,
                    "args": ["-c", "import sys; sys.exit(9)"],
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert json.loads(captured.out)["reviewed_cells"] == 0
    assert "review cell failure:" in captured.err
    states = {
        row["state"]
        for row in SessionStore(tmp_path).list_cells(json.loads(captured.out)["session_id"])
    }
    assert states == {"pending"}


def test_review_timeout_progress_and_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_review_repo(tmp_path, capsys)
    config = tmp_path / "review-gauntlet.json"
    config.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": sys.executable,
                    "args": ["-c", "import time; print('before', flush=True); time.sleep(2)"],
                    "timeout_seconds": 0.1,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["reviewed_cells"] == 0
    assert "review cell timeout:" in captured.err
    cell_id = data["failed_cell_id"]
    cell_dir = tmp_path / ".review-gauntlet" / "runs" / str(data["run_id"]) / "cells" / cell_id
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["timeout_seconds"] == 0.1
    assert (cell_dir / "stdout.txt").is_file()
    assert (cell_dir / "stderr.txt").is_file()
