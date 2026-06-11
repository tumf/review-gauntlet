from __future__ import annotations

import argparse
import json
import sys
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, NoReturn, cast

from review_gauntlet.config import ConfigError, load_config
from review_gauntlet.findings import FindingState, normalize_ocr_comment
from review_gauntlet.inventory import build_inventory, build_inventory_for_paths
from review_gauntlet.models import ReviewPlan
from review_gauntlet.ocr_rules import load_ruleset
from review_gauntlet.planner import build_matrix, build_plan
from review_gauntlet.report import render_markdown_report
from review_gauntlet.review_adapter import (
    CommandReviewAdapter,
    FakeReviewAdapter,
    ReviewAdapter,
    ReviewAdapterError,
    ReviewAdapterResult,
)
from review_gauntlet.review_cells import CellState, ReviewCell, cells_from_plan
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import (
    TargetSpec,
    changed_files_for_target,
    file_digests,
    resolve_target,
    target_digest,
)

USAGE_ERROR = 64


def fail(message: str, code: int = USAGE_ERROR) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review-gauntlet")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inventory", "plan"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("root", nargs="?", default=".")
        subparser.add_argument("--json", action="store_true", help="emit JSON output")
    report = subparsers.add_parser("report")
    report.add_argument("root", nargs="?", default=".")
    report.add_argument("--format", choices=("markdown", "json"), default="markdown")

    init = subparsers.add_parser("init")
    init.add_argument("root", nargs="?", default=".")
    init.add_argument("--from", dest="base_ref")
    init.add_argument("--to", dest="head_ref")
    init.add_argument("--worktree", action="store_true")
    init.add_argument("--commit")
    init.add_argument("--all", dest="all_files", action="store_true")
    init.add_argument("--format", choices=("human", "json"), default="human")
    init.add_argument("--audience", choices=("human", "agent"), default="human")

    review = subparsers.add_parser("review")
    review.add_argument("root", nargs="?", default=".")
    review.add_argument("--budget", type=int, default=50)
    review.add_argument("--concurrency", type=int, default=8)
    review.add_argument("--fixture", type=Path)
    review.add_argument("--config", type=Path)
    _session_output_args(review)

    status = subparsers.add_parser("status")
    status.add_argument("root", nargs="?", default=".")
    _session_output_args(status)

    findings = subparsers.add_parser("findings")
    findings.add_argument("root", nargs="?", default=".")
    findings.add_argument("--all", action="store_true")
    _session_output_args(findings)

    mark = subparsers.add_parser("mark")
    mark.add_argument("root", nargs="?", default=".")
    mark.add_argument("finding_id")
    mark.add_argument(
        "state", choices=("confirmed", "false-positive", "waived", "accepted-risk", "fixed")
    )
    mark.add_argument("--reason", default="")
    mark.add_argument("--owner", default="")
    mark.add_argument("--until", default="")
    _session_output_args(mark)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("root", nargs="?", default=".")
    _session_output_args(finalize)
    return parser


def _session_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument("--audience", choices=("human", "agent"), default="human")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        fail(f"root does not exist or is not a directory: {root}")

    if args.command in {"inventory", "plan", "report"}:
        _run_legacy_command(args, root)
        return
    try:
        _run_session_command(args, root)
    except ConfigError as exc:
        fail(str(exc))
    except ValueError as exc:
        fail(str(exc))
    except LookupError as exc:
        fail(str(exc), code=1)


def _run_legacy_command(args: argparse.Namespace, root: Path) -> None:
    inventory = build_inventory(root)
    if args.command == "inventory":
        print(inventory.model_dump_json(indent=2))
        return
    plan = build_plan(inventory)
    if args.command == "plan":
        print(plan.model_dump_json(indent=2))
        return
    matrix = build_matrix(plan)
    if args.format == "json":
        print(matrix.model_dump_json(indent=2))
        return
    print(render_markdown_report(plan, matrix))


def _run_session_command(args: argparse.Namespace, root: Path) -> None:
    store = SessionStore(root)
    if args.command == "init":
        _cmd_init(args, root, store)
    elif args.command == "review":
        _cmd_review(args, root, store)
    elif args.command == "status":
        _emit(_status(store, root), args.format)
    elif args.command == "findings":
        _emit(_findings(store, include_all=bool(args.all)), args.format)
    elif args.command == "mark":
        _cmd_mark(args, store)
    elif args.command == "finalize":
        result = _finalize(store, root)
        _emit(result, args.format)
        if not result["can_finalize"]:
            raise SystemExit(1)


def _cmd_init(args: argparse.Namespace, root: Path, store: SessionStore) -> None:
    target = resolve_target(
        root=root,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        worktree=bool(args.worktree),
        commit=args.commit,
        all_files=bool(args.all_files),
    )
    ruleset = load_ruleset()
    plan = _build_target_plan(root, target)
    cells = cells_from_plan(plan, file_digests(root))
    session_id = f"RGS-{uuid.uuid4().hex[:12]}"
    metadata = {
        "session_id": session_id,
        "root": str(root.resolve()),
        "target": target.model_dump(mode="json"),
        "ruleset_digest": ruleset.digest,
        "target_digest": target_digest(root),
    }
    store.create_session(metadata, cells)
    (store.state_dir / "rules.lock").write_text(ruleset.model_dump_json(indent=2), encoding="utf-8")
    _emit({"session_id": session_id, "cell_count": len(cells), "run_count": 0}, args.format)


def _build_target_plan(root: Path, target: TargetSpec) -> ReviewPlan:
    changed_paths = changed_files_for_target(root, target)
    inventory = (
        build_inventory(root)
        if changed_paths is None
        else build_inventory_for_paths(root, changed_paths)
    )
    return build_plan(inventory)


def _cmd_review(args: argparse.Namespace, root: Path, store: SessionStore) -> None:
    if args.concurrency < 1:
        fail("review --concurrency must be a positive integer")
    session_id = store.active_session_id()
    metadata = store.session_metadata(session_id)
    ruleset = load_ruleset()
    digest = target_digest(root)
    target = TargetSpec.model_validate(metadata["target"])
    _reconcile_cells(store, root, target)
    run_id = store.create_run(session_id, digest)
    if args.budget <= 0:
        status = _status(store, root)
        _emit(
            {"run_id": run_id, "reviewed_cells": 0, "finding_ids": [], **status},
            args.format,
        )
        return
    adapter_config = load_config(root, args.config) if args.fixture is None else None
    if args.fixture is not None:
        adapter: ReviewAdapter = FakeReviewAdapter(args.fixture)
    elif adapter_config is not None:
        _config_path, config = adapter_config
        adapter = CommandReviewAdapter(
            config=config.adapter,
            root=root,
            state_dir=store.state_dir,
            run_id=run_id,
            ruleset=ruleset,
        )
    else:
        raise ValueError("review requires --fixture or a command adapter config")

    current_cells = cells_from_plan(_build_target_plan(root, target), file_digests(root))
    selected_cells = _select_review_cells(
        store=store,
        session_id=session_id,
        current_cells=current_cells,
        budget=args.budget,
    )
    results = _review_cells_concurrently(adapter, selected_cells, concurrency=args.concurrency)

    reviewed = 0
    finding_ids: list[str] = []
    seen_fingerprints: set[str] = set()
    evaluated_paths: set[str] = set()
    for selected in selected_cells:
        outcome = results[selected.id]
        if isinstance(outcome, ReviewAdapterError):
            status = _status(store, root)
            _emit(
                {
                    "run_id": run_id,
                    "reviewed_cells": reviewed,
                    "failed_cell_id": selected.id,
                    "error": str(outcome),
                    "failure": outcome.failure,
                    **status,
                },
                args.format,
            )
            raise SystemExit(1) from outcome
        evaluated_paths.add(selected.file_path)
        for comment in outcome.comments:
            finding = normalize_ocr_comment(
                comment,
                repository_id=str(root.resolve()),
                base_target=json.dumps(metadata["target"], sort_keys=True),
                rule_id=selected.rule_id,
                ruleset_digest=ruleset.digest,
            )
            seen_fingerprints.add(finding.fingerprint)
            finding_ids.append(store.upsert_finding(session_id, run_id, selected.id, finding))
        store.update_cell_state(selected.id, CellState.REVIEWED)
        reviewed += 1
    store.verify_fixed_findings(session_id, seen_fingerprints, evaluated_paths)
    status = _status(store, root)
    _emit(
        {"run_id": run_id, "reviewed_cells": reviewed, "finding_ids": finding_ids, **status},
        args.format,
    )


def _select_review_cells(
    *,
    store: SessionStore,
    session_id: str,
    current_cells: tuple[ReviewCell, ...],
    budget: int,
) -> list[ReviewCell]:
    cell_map = {cell.id: cell for cell in current_cells}
    fixed_pending_paths = store.fixed_pending_paths(session_id)
    selected: list[ReviewCell] = []
    for row in store.list_cells(session_id):
        if len(selected) >= budget:
            break
        if (
            row["state"] not in {CellState.PENDING, CellState.STALE}
            and row["file_path"] not in fixed_pending_paths
        ):
            continue
        cell = cell_map.get(str(row["cell_id"]))
        if cell is not None:
            selected.append(cell)
    return selected


def _review_cells_concurrently(
    adapter: ReviewAdapter,
    cells: list[ReviewCell],
    *,
    concurrency: int,
) -> dict[str, ReviewAdapterResult | ReviewAdapterError]:
    if not cells:
        return {}
    results: dict[str, ReviewAdapterResult | ReviewAdapterError] = {}
    max_workers = min(concurrency, len(cells))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[str, Future[ReviewAdapterResult]] = {
            cell.id: executor.submit(adapter.review, cell) for cell in cells
        }
        for cell in cells:
            try:
                results[cell.id] = futures[cell.id].result()
            except ReviewAdapterError as exc:
                results[cell.id] = exc
    return results


def _reconcile_cells(store: SessionStore, root: Path, target: TargetSpec) -> None:
    session_id = store.active_session_id()
    current = {
        cell.id: cell
        for cell in cells_from_plan(_build_target_plan(root, target), file_digests(root))
    }
    existing = {str(row["cell_id"]): row for row in store.list_cells(session_id)}
    new_cells = tuple(cell for cell_id, cell in current.items() if cell_id not in existing)
    store.add_cells(session_id, new_cells)
    for cell_id, row in existing.items():
        current_cell = current.get(cell_id)
        if current_cell is None:
            store.update_cell_state(cell_id, CellState.SUPERSEDED)
        elif row["content_digest"] != current_cell.content_digest:
            store.update_cell_state(cell_id, CellState.STALE)


def _cmd_mark(args: argparse.Namespace, store: SessionStore) -> None:
    mapping = {
        "confirmed": FindingState.CONFIRMED,
        "false-positive": FindingState.FALSE_POSITIVE,
        "waived": FindingState.WAIVED,
        "accepted-risk": FindingState.ACCEPTED_RISK,
        "fixed": FindingState.FIXED_PENDING_VERIFICATION,
    }
    metadata = {"owner": args.owner, "until": args.until}
    store.mark_finding(args.finding_id, mapping[args.state], args.reason, metadata)
    _emit({"finding_id": args.finding_id, "state": mapping[args.state]}, args.format)


def _status(store: SessionStore, root: Path) -> dict[str, object]:
    session_id = store.active_session_id()
    with store.connect() as conn:
        cell_counts = dict(
            conn.execute(
                """
                select state, count(*) as count
                from review_cells
                where session_id = ?
                group by state
                """,
                (session_id,),
            ).fetchall()
        )
        finding_counts = dict(
            conn.execute(
                "select state, count(*) as count from findings where session_id = ? group by state",
                (session_id,),
            ).fetchall()
        )
        run_count = conn.execute(
            "select count(*) as count from runs where session_id = ?", (session_id,)
        ).fetchone()["count"]
    reasons = _finalize_reasons(cell_counts, finding_counts, store, session_id, root)
    return {
        "session_id": session_id,
        "session_state": "active",
        "coverage": cell_counts,
        "finding_state_counts": finding_counts,
        "run_count": int(run_count),
        "can_finalize": not reasons,
        "finalize_blockers": reasons,
        "next_required_action": _next_action(cell_counts, finding_counts, reasons),
    }


def _findings(store: SessionStore, *, include_all: bool) -> dict[str, object]:
    session_id = store.active_session_id()
    terminal = {"fixed_verified", "false_positive", "waived", "accepted_risk"}
    with store.connect() as conn:
        rows = list(conn.execute("select * from findings where session_id = ?", (session_id,)))
    findings = [dict(row) for row in rows if include_all or row["state"] not in terminal]
    return {"session_id": session_id, "findings": findings}


def _finalize(store: SessionStore, root: Path) -> dict[str, object]:
    status = _status(store, root)
    if status["can_finalize"]:
        with store.connect() as conn:
            conn.execute(
                "update sessions set state = 'finalized' where session_id = ?",
                (status["session_id"],),
            )
        status["session_state"] = "finalized"
    return status


def _finalize_reasons(
    cell_counts: dict[str, int],
    finding_counts: dict[str, int],
    store: SessionStore,
    session_id: str,
    root: Path,
) -> list[str]:
    reasons: list[str] = []
    if cell_counts.get("pending", 0):
        reasons.append("review cells are still pending")
    if cell_counts.get("stale", 0):
        reasons.append("review cells are stale after target changes")
    for state in ("untriaged", "confirmed", "reopened"):
        if finding_counts.get(state, 0):
            reasons.append(f"findings remain {state}")
    if finding_counts.get("fixed_pending_verification", 0):
        reasons.append("fixed findings require verification")
    if _expired_terminal_decision_count(store, session_id):
        reasons.append("waived or accepted-risk findings have expired")
    last_reviewed_digest = store.last_run_target_digest(session_id)
    if last_reviewed_digest is None:
        reasons.append("no review run has been completed")
    elif last_reviewed_digest != target_digest(root):
        reasons.append("target digest has changed since the last review run")
    return reasons


def _expired_terminal_decision_count(store: SessionStore, session_id: str) -> int:
    today = datetime.now(UTC).date()
    with store.connect() as conn:
        rows = conn.execute(
            """
            select finding_id, state
            from findings
            where session_id = ? and state in ('waived', 'accepted_risk')
            """,
            (session_id,),
        ).fetchall()
        expired = 0
        for row in rows:
            event = conn.execute(
                """
                select metadata from finding_events
                where finding_id = ? and to_state = ?
                order by event_id desc
                limit 1
                """,
                (row["finding_id"], row["state"]),
            ).fetchone()
            if event is not None and _is_expired(str(event["metadata"]), today):
                expired += 1
    return expired


def _is_expired(metadata_json: str, today: date) -> bool:
    raw_metadata = json.loads(metadata_json)
    if not isinstance(raw_metadata, dict):
        raise ValueError("finding event metadata must be a JSON object")
    metadata = cast(dict[str, Any], raw_metadata)
    until = metadata.get("until")
    if not until:
        return False
    return date.fromisoformat(str(until)) < today


def _next_action(
    cell_counts: dict[str, int], finding_counts: dict[str, int], reasons: list[str]
) -> str:
    if (
        finding_counts.get("untriaged", 0)
        or finding_counts.get("confirmed", 0)
        or finding_counts.get("reopened", 0)
    ):
        return "triage_findings"
    if finding_counts.get("fixed_pending_verification", 0):
        return "run_review_to_verify_fixes"
    if cell_counts.get("pending", 0) or cell_counts.get("stale", 0):
        return "run_review"
    if reasons:
        return "resolve_finalize_blockers"
    return "finalize"


def _emit(result: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    for key, value in result.items():
        print(f"{key}: {value}")
