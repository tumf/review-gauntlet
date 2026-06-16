from __future__ import annotations

import json
import os
import shutil
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from review_gauntlet.findings import FindingState
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import HeadMode, TargetKind, TargetSpec, target_digest

CHECKPOINT_SCHEMA_VERSION = 1
STANDARD_CHECKPOINT_ARTIFACTS = ("status.json", "findings.json", "events.json", "summary.md")
TERMINAL_DECISION_STATES = {FindingState.WAIVED.value, FindingState.ACCEPTED_RISK.value}


@dataclass(frozen=True)
class DirtyReviewUniverseError(ValueError):
    paths: tuple[str, ...]

    def __str__(self) -> str:
        return "review-universe files are dirty relative to HEAD"


@dataclass(frozen=True)
class DirtyWorkingTree:
    review_paths: tuple[str, ...]
    non_review_paths: tuple[str, ...]

    @property
    def is_dirty(self) -> bool:
        return bool(self.review_paths or self.non_review_paths)


@dataclass(frozen=True)
class CheckpointCommitResult:
    attempted: bool
    committed: bool
    commit: str | None
    reason: str
    blocked_paths: tuple[str, ...] = ()
    failed_error: str | None = None

    def model_dump(self) -> dict[str, object]:
        result: dict[str, object] = {
            "checkpoint_commit_attempted": self.attempted,
            "checkpoint_committed": self.committed,
            "checkpoint_commit": self.commit,
            "checkpoint_commit_reason": self.reason,
        }
        if self.blocked_paths:
            result["checkpoint_commit_blocked_paths"] = list(self.blocked_paths)
        if self.failed_error is not None:
            result["checkpoint_commit_error"] = self.failed_error
        return result


def latest_checkpoint_dir(root: Path) -> Path:
    pointer = root / ".review-gauntlet" / "checkpoints" / "latest"
    invalid = pointer.parent / "__invalid_latest_checkpoint_pointer__"
    if pointer.is_symlink() or pointer.is_dir():
        return invalid
    if pointer.is_file():
        try:
            checkpoint_id = pointer.read_text(encoding="utf-8").strip()
        except OSError:
            return invalid
        else:
            if checkpoint_id and (
                not any(part in {"", ".", ".."} for part in Path(checkpoint_id).parts)
                and Path(checkpoint_id).name == checkpoint_id
            ):
                candidate = pointer.parent / checkpoint_id
                if candidate.is_dir() and not candidate.is_symlink():
                    return candidate
        return invalid
    return invalid


def latest_checkpoint_pointer(root: Path) -> Path:
    return root / ".review-gauntlet" / "checkpoints" / "latest"


def load_latest_checkpoint(root: Path) -> dict[str, Any] | None:
    status_path = latest_checkpoint_dir(root) / "status.json"
    if not status_path.exists():
        return None
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("latest checkpoint status.json is invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("latest checkpoint status.json must contain a JSON object")
    return cast(dict[str, Any], data)


def target_from_latest_checkpoint(root: Path) -> TargetSpec | None:
    checkpoint = load_latest_checkpoint(root)
    if checkpoint is None:
        return None
    _validate_latest_checkpoint(root, checkpoint)
    base = checkpoint["review_base_commit"]
    if not isinstance(base, str):
        raise ValueError("latest checkpoint review_base_commit must be a string")
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    return TargetSpec(
        kind=TargetKind.BRANCH, base_ref=base, head_ref=head, head_mode=HeadMode.MOVING
    )


def _validate_latest_checkpoint(root: Path, checkpoint: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "checkpoint_id",
        "checkpoint_state",
        "usable_as_review_base",
        "review_base_commit",
    }
    missing = sorted(required - set(checkpoint))
    if missing:
        raise ValueError(f"latest checkpoint is missing required fields: {', '.join(missing)}")
    if checkpoint["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("latest checkpoint schema_version is not supported")
    if checkpoint["checkpoint_state"] != "complete":
        raise ValueError("latest checkpoint is not complete")
    if checkpoint["usable_as_review_base"] is not True:
        raise ValueError("latest checkpoint is not usable as review base")
    checkpoint_id = checkpoint["checkpoint_id"]
    if not isinstance(checkpoint_id, str):
        raise ValueError("latest checkpoint checkpoint_id must be a string")
    if checkpoint_id != latest_checkpoint_dir(root).name:
        raise ValueError("latest checkpoint checkpoint_id does not match checkpoint directory")
    for name in ("findings.json", "events.json"):
        path = latest_checkpoint_dir(root) / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"latest checkpoint is internally inconsistent: missing {name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"latest checkpoint {name} is invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
        checkpoint_file = cast(dict[str, Any], data)
        if checkpoint_file.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(f"latest checkpoint {name} schema_version is not supported")
        if checkpoint_file.get("checkpoint_id") != checkpoint_id:
            raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
        payload_key = "findings" if name == "findings.json" else "events"
        raw_payload = checkpoint_file.get(payload_key)
        if not isinstance(raw_payload, list):
            raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
        payload = cast(list[Any], raw_payload)
        required_entry_fields = (
            ("finding_id", "session_id", "fingerprint", "state", "path", "rule_id", "content")
            if name == "findings.json"
            else ("event_id", "finding_id", "from_state", "to_state", "reason")
        )
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
            entry = cast(dict[str, Any], item)
            if entry.get("checkpoint_id") != checkpoint_id:
                raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
            if any(field not in entry for field in required_entry_fields):
                raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
            if name == "findings.json":
                if not all(isinstance(entry[field], str) for field in required_entry_fields):
                    raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
                if entry["state"] not in {state.value for state in FindingState}:
                    raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
            else:
                if not isinstance(entry["event_id"], int) or isinstance(entry["event_id"], bool):
                    raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
                text_fields = ("finding_id", "from_state", "to_state", "reason")
                if not all(isinstance(entry[field], str) for field in text_fields):
                    raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
                valid_transition_states = {state.value for state in FindingState}
                if entry["from_state"] not in valid_transition_states:
                    raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
                if entry["to_state"] not in valid_transition_states:
                    raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
    summary = latest_checkpoint_dir(root) / "summary.md"
    if not summary.is_file() or summary.is_symlink():
        raise ValueError("latest checkpoint is internally inconsistent: missing summary.md")
    base = checkpoint["review_base_commit"]
    if not isinstance(base, str):
        raise ValueError("latest checkpoint review_base_commit must be a string")
    try:
        resolved_base = _git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            "latest checkpoint review_base_commit does not resolve to a commit"
        ) from exc
    if base != resolved_base:
        raise ValueError(
            "latest checkpoint review_base_commit must be a resolved commit SHA, not a mutable ref"
        )
    try:
        _git(root, "merge-base", "--is-ancestor", resolved_base, "HEAD")
    except subprocess.CalledProcessError as exc:
        raise ValueError("latest checkpoint review_base_commit is not an ancestor of HEAD") from exc


def assert_review_universe_clean(root: Path) -> None:
    dirty = _dirty_review_universe_paths(root)
    if dirty:
        raise DirtyReviewUniverseError(dirty)


def _dirty_review_universe_paths(root: Path) -> tuple[str, ...]:
    if not (root / ".git").exists():
        return ()
    names = _split(_git(root, "diff", "--name-only", "--cached"))
    names += _split(_git(root, "diff", "--name-only"))
    names += _split(_git(root, "ls-files", "--others", "--exclude-standard"))
    from review_gauntlet.inventory import should_include_review_relative_path

    return tuple(
        sorted(
            {
                name
                for name in names
                if not name.startswith(".review-gauntlet/")
                and should_include_review_relative_path(name)
            }
        )
    )


def _get_all_uncommitted_paths(root: Path) -> tuple[str, ...]:
    if not (root / ".git").exists():
        return ()
    names = _split(_git(root, "diff", "--name-only", "--cached"))
    names += _split(_git(root, "diff", "--name-only"))
    names += _split(_git(root, "ls-files", "--others", "--exclude-standard"))
    return tuple(sorted({name for name in names}))


def classify_working_tree_dirty(root: Path) -> DirtyWorkingTree:
    from review_gauntlet.inventory import should_include_review_relative_path

    all_paths = tuple(
        p for p in _get_all_uncommitted_paths(root) if not p.startswith(".review-gauntlet/")
    )
    review_paths = tuple(p for p in all_paths if should_include_review_relative_path(p))
    non_review_paths = tuple(p for p in all_paths if not should_include_review_relative_path(p))
    return DirtyWorkingTree(
        review_paths=review_paths,
        non_review_paths=non_review_paths,
    )


def write_latest_checkpoint(
    store: SessionStore, root: Path, session_id: str, status: dict[str, object]
) -> dict[str, object]:
    assert_review_universe_clean(root)
    head = _head_commit(root)
    if (
        not session_id.isascii()
        or not session_id.replace("-", "").replace("_", "").isalnum()
        or any(part in {"", ".", ".."} for part in Path(session_id).parts)
        or Path(session_id).name != session_id
    ):
        raise ValueError("session_id must be a single path-safe segment")
    checkpoint_id = f"RGC-{head[:12]}-{session_id}"
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    metadata = store.session_metadata(session_id)
    last_digest = store.last_run_target_digest(session_id)
    base_status = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "checkpoint_id": checkpoint_id,
        "checkpoint_state": "complete",
        "usable_as_review_base": True,
        "review_base_commit": head,
        "head_commit": head,
        "created_at": generated_at,
        "next_required_action": "init_next_session",
        "session_id": session_id,
        "session_metadata": metadata,
        "target": metadata.get("target"),
        "target_digest": target_digest(root),
        "last_run_target_digest": last_digest,
        "ruleset_digest": metadata.get("ruleset_digest"),
        "coverage": status.get("coverage", {}),
        "finding_state_counts": status.get("finding_state_counts", {}),
        "run_count": status.get("run_count", 0),
        "blockers": status.get("finalize_blockers", []),
    }
    findings = _checkpoint_findings(store, session_id, checkpoint_id)
    events = _checkpoint_events(store, session_id, checkpoint_id)
    files = {
        "status.json": base_status,
        "findings.json": {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_id": checkpoint_id,
            "findings": findings,
        },
        "events.json": {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_id": checkpoint_id,
            "events": events,
        },
    }
    summary = _render_summary(base_status, findings, events)
    pointer_path = latest_checkpoint_pointer(root)
    checkpoints_dir = pointer_path.parent
    checkpoint_dir = checkpoints_dir / checkpoint_id
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = checkpoints_dir / f".{checkpoint_id}.tmp-{os.getpid()}"
    backup_dir = checkpoints_dir / f".{checkpoint_id}.bak-{os.getpid()}"
    pointer_backup_dir = checkpoints_dir / f".latest.bak-{os.getpid()}-{checkpoint_id}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    if pointer_backup_dir.exists():
        shutil.rmtree(pointer_backup_dir)
    tmp_dir.mkdir(parents=True)
    pointer_tmp = checkpoints_dir / f".latest.tmp-{os.getpid()}-{checkpoint_id}"
    try:
        for filename, data in files.items():
            (tmp_dir / filename).write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        (tmp_dir / "summary.md").write_text(summary, encoding="utf-8")
        if checkpoint_dir.exists():
            checkpoint_dir.rename(backup_dir)
        tmp_dir.rename(checkpoint_dir)
        pointer_tmp.write_text(checkpoint_id + "\n", encoding="utf-8")
        if pointer_path.is_dir():
            pointer_path.rename(pointer_backup_dir)
        pointer_tmp.replace(pointer_path)
        with suppress(OSError):
            if pointer_backup_dir.exists():
                shutil.rmtree(pointer_backup_dir)
    except Exception:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        if checkpoint_dir.exists() and backup_dir.exists():
            shutil.rmtree(checkpoint_dir)
        if backup_dir.exists():
            backup_dir.rename(checkpoint_dir)
        if pointer_backup_dir.exists():
            if pointer_path.is_dir():
                shutil.rmtree(pointer_path)
            else:
                pointer_path.unlink(missing_ok=True)
            pointer_backup_dir.rename(pointer_path)
        with suppress(OSError):
            pointer_tmp.unlink(missing_ok=True)
        raise
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    generated_files = [
        str((checkpoint_dir / name).relative_to(root)) for name in STANDARD_CHECKPOINT_ARTIFACTS
    ]
    return {
        "checkpoint_id": checkpoint_id,
        "checkpoint_dir": str(checkpoint_dir.relative_to(root)),
        "checkpoint_state": "complete",
        "usable_as_review_base": True,
        "review_base_commit": head,
        "generated_files": generated_files,
        "next_required_action": "init_next_session",
    }


def _checkpoint_findings(
    store: SessionStore, session_id: str, checkpoint_id: str
) -> list[dict[str, Any]]:
    with store.connect() as conn:
        rows = conn.execute(
            "select * from findings where session_id = ? order by finding_id", (session_id,)
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            occurrence = conn.execute(
                """
                select * from finding_occurrences
                where finding_id = ?
                order by occurrence_id desc
                limit 1
                """,
                (row["finding_id"],),
            ).fetchone()
            item = dict(row)
            item["checkpoint_id"] = checkpoint_id
            if occurrence is not None:
                item["latest_occurrence"] = dict(occurrence)
            result.append(item)
        return result


def _checkpoint_events(
    store: SessionStore, session_id: str, checkpoint_id: str
) -> list[dict[str, Any]]:
    with store.connect() as conn:
        rows = conn.execute(
            """
            select e.* from finding_events e
            join findings f on f.finding_id = e.finding_id
            where f.session_id = ?
            order by e.event_id
            """,
            (session_id,),
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["checkpoint_id"] = checkpoint_id
        metadata = str(item.pop("metadata"))
        try:
            item["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            item["metadata_raw"] = metadata
        events.append(item)
    return events


def _render_summary(
    status: dict[str, Any], findings: list[dict[str, Any]], events: list[dict[str, Any]]
) -> str:
    lines = [
        "# Review Gauntlet Checkpoint",
        "",
        f"- Checkpoint state: {status['checkpoint_state']}",
        f"- Usable as review base: {status['usable_as_review_base']}",
        f"- Review base commit: {status['review_base_commit']}",
        f"- Session ID: {status['session_id']}",
        f"- Created at: {status['created_at']} (generation timestamp)",
        "",
        "## Coverage",
        "",
        "| State | Count |",
        "| --- | ---: |",
    ]
    coverage = cast(dict[str, Any], status.get("coverage", {}))
    for state, count in sorted(coverage.items()):
        lines.append(f"| {_escape_md(str(state))} | {count} |")
    lines += [
        "",
        "## Findings",
        "",
        "| ID | State | Path | Rule | Content |",
        "| --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        lines.append(
            "| {finding_id} | {state} | {path} | {rule_id} | {content} |".format(
                finding_id=_escape_md(str(finding.get("finding_id", ""))),
                state=_escape_md(str(finding.get("state", ""))),
                path=_escape_md(str(finding.get("path", ""))),
                rule_id=_escape_md(str(finding.get("rule_id", ""))),
                content=_escape_md(str(finding.get("content", ""))),
            )
        )
    lines += [
        "",
        "## Triage Events",
        "",
        "| Event | Finding | From | To | Reason |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for event in events:
        lines.append(
            f"| {event.get('event_id')} | {_escape_md(str(event.get('finding_id', '')))} | "
            f"{_escape_md(str(event.get('from_state', '')))} | "
            f"{_escape_md(str(event.get('to_state', '')))} | "
            f"{_escape_md(str(event.get('reason', '')))} |"
        )
    blockers = cast(list[Any], status.get("blockers", []))
    lines += ["", "## Blockers", ""]
    lines.append("None" if not blockers else "\n".join(f"- {_escape_md(str(b))}" for b in blockers))
    return "\n".join(lines) + "\n"


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def commit_latest_checkpoint(
    root: Path, *, session_id: str, generated_files: tuple[str, ...] = ()
) -> CheckpointCommitResult:
    if not (root / ".git").exists():
        return CheckpointCommitResult(
            attempted=True, committed=False, commit=None, reason="not_git_repository"
        )
    dirty = _get_all_uncommitted_paths(root)
    allowed_paths = _allowed_checkpoint_commit_paths(root, generated_files)
    staged_before = _split(_git(root, "diff", "--cached", "--name-only"))
    unstaged_before = _split(_git(root, "diff", "--name-only"))
    staged_and_unstaged_paths = tuple(
        path for path in staged_before if path in unstaged_before and path in allowed_paths
    )
    if staged_and_unstaged_paths:
        return CheckpointCommitResult(
            attempted=True,
            committed=False,
            commit=None,
            reason="blocked_by_staged_and_unstaged_checkpoint_changes",
            blocked_paths=staged_and_unstaged_paths,
        )
    paths_to_stage = tuple(path for path in dirty if path not in staged_before)
    blocked_paths = tuple(path for path in dirty if path not in allowed_paths)
    if blocked_paths:
        return CheckpointCommitResult(
            attempted=True,
            committed=False,
            commit=None,
            reason="blocked_by_non_checkpoint_changes",
            blocked_paths=blocked_paths,
        )
    checkpoint_dirty = tuple(path for path in dirty if path in allowed_paths)
    if not checkpoint_dirty:
        return CheckpointCommitResult(
            attempted=True, committed=False, commit=None, reason="no_checkpoint_diff"
        )
    try:
        if paths_to_stage:
            _git(root, "add", "--", *paths_to_stage)
        staged = _split(_git(root, "diff", "--cached", "--name-only", "--", *checkpoint_dirty))
        if not staged:
            return CheckpointCommitResult(
                attempted=True, committed=False, commit=None, reason="no_checkpoint_diff"
            )
        commit_message = f"checkpoint: finalize review-gauntlet session {session_id}"
        _git(root, "commit", "-m", commit_message, "--", *staged)
        commit = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    except subprocess.CalledProcessError as exc:
        if paths_to_stage:
            with suppress(subprocess.CalledProcessError):
                _git(root, "restore", "--staged", "--", *paths_to_stage)
        return CheckpointCommitResult(
            attempted=True,
            committed=False,
            commit=None,
            reason="git_failure",
            failed_error=_git_error(exc),
        )
    return CheckpointCommitResult(attempted=True, committed=True, commit=commit, reason="committed")


def _allowed_checkpoint_commit_paths(
    root: Path, generated_files: tuple[str, ...]
) -> tuple[str, ...]:
    allowed = {".review-gauntlet/checkpoints/latest"}
    allowed.update(_safe_latest_checkpoint_artifact_paths(root))
    for path in generated_files:
        if _is_allowed_checkpoint_artifact_path(path):
            allowed.add(path)
    return tuple(sorted(allowed))


def _safe_latest_checkpoint_artifact_paths(root: Path) -> tuple[str, ...]:
    pointer = latest_checkpoint_pointer(root)
    if pointer.is_symlink() or pointer.is_dir() or not pointer.is_file():
        return ()
    try:
        checkpoint_id = pointer.read_text(encoding="utf-8").strip()
    except OSError:
        return ()
    if not _is_path_safe_checkpoint_id(checkpoint_id):
        return ()
    checkpoint_dir = pointer.parent / checkpoint_id
    if not checkpoint_dir.is_dir() or checkpoint_dir.is_symlink():
        return ()
    try:
        checkpoint_dir.resolve().relative_to(pointer.parent.resolve())
    except ValueError:
        return ()
    return tuple(
        (checkpoint_dir / filename).relative_to(root).as_posix()
        for filename in STANDARD_CHECKPOINT_ARTIFACTS
    )


def _is_allowed_checkpoint_artifact_path(path: str) -> bool:
    relative = Path(path)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return False
    parts = relative.parts
    if parts == (".review-gauntlet", "checkpoints", "latest"):
        return True
    if len(parts) == 4 and parts[:2] == (".review-gauntlet", "checkpoints"):
        checkpoint_id, filename = parts[2], parts[3]
        return (
            _is_path_safe_checkpoint_id(checkpoint_id) and filename in STANDARD_CHECKPOINT_ARTIFACTS
        )
    return False


def _is_path_safe_checkpoint_id(checkpoint_id: str) -> bool:
    return (
        checkpoint_id.startswith("RGC-")
        and checkpoint_id != "RGC-"
        and checkpoint_id.isascii()
        and checkpoint_id.replace("-", "").replace("_", "").isalnum()
        and not any(part in {"", ".", ".."} for part in Path(checkpoint_id).parts)
        and Path(checkpoint_id).name == checkpoint_id
    )


def _git_error(exc: subprocess.CalledProcessError) -> str:
    stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else ""
    stdout = exc.stdout.strip() if isinstance(exc.stdout, str) else ""
    detail = stderr or stdout or str(exc)
    return detail


def _split(output: str) -> tuple[str, ...]:
    return tuple(line for line in output.splitlines() if line)


def _head_commit(root: Path) -> str:
    if not (root / ".git").exists():
        return "no-git-head"
    return _git(root, "rev-parse", "--verify", "HEAD^{commit}")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, timeout=10, check=True
    )
    return completed.stdout.strip()
