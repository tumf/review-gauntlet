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
TERMINAL_DECISION_STATES = {FindingState.WAIVED.value, FindingState.ACCEPTED_RISK.value}


@dataclass(frozen=True)
class DirtyReviewUniverseError(ValueError):
    paths: tuple[str, ...]

    def __str__(self) -> str:
        return "review-universe files are dirty relative to HEAD: " + ", ".join(self.paths)


@dataclass(frozen=True)
class DirtyWorkingTree:
    review_paths: tuple[str, ...]
    non_review_paths: tuple[str, ...]

    @property
    def is_dirty(self) -> bool:
        return bool(self.review_paths or self.non_review_paths)


def latest_checkpoint_dir(root: Path) -> Path:
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
    for name in ("findings.json", "events.json"):
        path = latest_checkpoint_dir(root) / name
        if not path.exists():
            raise ValueError(f"latest checkpoint is internally inconsistent: missing {name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"latest checkpoint {name} is invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
        checkpoint_file = cast(dict[str, Any], data)
        if checkpoint_file.get("checkpoint_id") != checkpoint_id:
            raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
        payload_key = "findings" if name == "findings.json" else "events"
        if not isinstance(checkpoint_file.get(payload_key), list):
            raise ValueError(f"latest checkpoint is internally inconsistent: {name}")
    summary = latest_checkpoint_dir(root) / "summary.md"
    if not summary.exists():
        raise ValueError("latest checkpoint is internally inconsistent: missing summary.md")
    base = checkpoint["review_base_commit"]
    if not isinstance(base, str):
        raise ValueError("latest checkpoint review_base_commit must be a string")
    try:
        _git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
        _git(root, "merge-base", "--is-ancestor", base, "HEAD")
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

    return tuple(sorted({name for name in names if should_include_review_relative_path(name)}))


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
        "findings.json": {"checkpoint_id": checkpoint_id, "findings": findings},
        "events.json": {"checkpoint_id": checkpoint_id, "events": events},
    }
    summary = _render_summary(base_status, findings, events)
    checkpoint_dir = latest_checkpoint_dir(root)
    tmp_dir = checkpoint_dir.parent / f".latest.tmp-{os.getpid()}-{checkpoint_id}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    old_dir: Path | None = None
    try:
        for filename, data in files.items():
            (tmp_dir / filename).write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        (tmp_dir / "summary.md").write_text(summary, encoding="utf-8")
        if checkpoint_dir.exists():
            old_dir = checkpoint_dir.parent / f".latest.old-{os.getpid()}-{checkpoint_id}"
            if old_dir.exists():
                shutil.rmtree(old_dir)
            checkpoint_dir.rename(old_dir)
            tmp_dir.rename(checkpoint_dir)
            with suppress(OSError):
                shutil.rmtree(old_dir)
        else:
            checkpoint_dir.parent.mkdir(parents=True, exist_ok=True)
            tmp_dir.rename(checkpoint_dir)
    except Exception:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        if old_dir is not None and old_dir.exists() and not checkpoint_dir.exists():
            old_dir.rename(checkpoint_dir)
        raise
    generated_files = [
        str((checkpoint_dir / name).relative_to(root))
        for name in ("status.json", "findings.json", "events.json", "summary.md")
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
