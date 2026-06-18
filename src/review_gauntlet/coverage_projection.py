from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from review_gauntlet.inventory import (
    build_inventory,
    build_inventory_for_paths,
    should_include_review_relative_path,
)
from review_gauntlet.models import Inventory, ReviewPlan
from review_gauntlet.planner import build_plan
from review_gauntlet.review_cells import cells_from_plan
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import TargetSpec, changed_files_for_target, file_digests

ACTIONABLE_FINDING_STATES = frozenset({"open"})
HIGH_RISK_RULE_WEIGHTS: dict[str, int] = {
    "secret-handling": 120,
    "path-safety": 110,
    "process-exec": 100,
    "data-validation": 80,
    "cli-contract": 60,
    "ci-reproducibility": 50,
    "test-evidence": 40,
    "docs-accuracy": 20,
}
TERMINAL_CELL_STATES = frozenset({"reviewed", "covered", "done"})
CoveragePriorityLabel = Literal["P0", "P1", "P2", "P3"]


@dataclass(frozen=True)
class CoverageCellInput:
    cell_id: str
    file_path: str
    rule_id: str
    slice_id: str
    state: str
    content_digest: str = ""


@dataclass(frozen=True)
class CoverageFindingInput:
    finding_id: str
    file_path: str
    rule_id: str
    state: str
    content: str
    latest_cell_id: str | None = None


@dataclass(frozen=True)
class QueueEntry:
    cell_id: str
    file_path: str
    rule_id: str
    slice_id: str
    state: str
    priority_label: CoveragePriorityLabel
    priority_score: int
    finding_count: int
    actionable_finding_count: int
    stale_reason: str | None
    why: str
    changed_since_review: bool


@dataclass(frozen=True)
class RuleCoverageSummary:
    rule_id: str
    total: int
    reviewed: int
    pending: int
    stale: int
    actionable_findings: int
    priority_label: CoveragePriorityLabel


@dataclass(frozen=True)
class FileCoverageSummary:
    file_path: str
    total: int
    reviewed: int
    pending: int
    stale: int
    actionable_findings: int
    highest_priority_label: CoveragePriorityLabel
    highest_priority_score: int


@dataclass(frozen=True)
class FindingSummaryEntry:
    finding_id: str
    file_path: str
    rule_id: str
    state: str
    content: str
    latest_cell_id: str | None
    actionable: bool


@dataclass(frozen=True)
class CoverageProjection:
    queue: tuple[QueueEntry, ...]
    rules: tuple[RuleCoverageSummary, ...]
    files: tuple[FileCoverageSummary, ...]
    findings: tuple[FindingSummaryEntry, ...]


@dataclass(frozen=True)
class CoverageCellFilter:
    stale: bool = False
    pending: bool = False
    blockers: bool = False
    open_findings: bool = False
    rule_prefix: str = ""
    file_prefix: str = ""


def empty_coverage_projection() -> CoverageProjection:
    return CoverageProjection(queue=(), rules=(), files=(), findings=())


def build_session_coverage_projection(
    store: SessionStore, session_id: str, root: Path
) -> CoverageProjection:
    metadata = store.session_metadata(session_id)
    target = TargetSpec.model_validate(metadata["target"])
    current_digests = file_digests(root)
    current_cells = {
        cell.id: cell for cell in cells_from_plan(_build_target_plan(root, target), current_digests)
    }
    persisted_cells = {str(row["cell_id"]): row for row in store.list_cells(session_id)}
    cells: list[CoverageCellInput] = []
    changed_files: set[str] = set()
    for cell_id, current_cell in current_cells.items():
        row = persisted_cells.get(cell_id)
        state = "pending" if row is None else str(row["state"])
        if row is not None and row["content_digest"] != current_cell.content_digest:
            changed_files.add(current_cell.file_path)
        cells.append(
            CoverageCellInput(
                cell_id=cell_id,
                file_path=current_cell.file_path,
                rule_id=current_cell.rule_id,
                slice_id=current_cell.slice_id,
                state=state,
                content_digest=current_cell.content_digest,
            )
        )
    return build_coverage_projection(
        tuple(cells), _session_findings(store, session_id), changed_files=frozenset(changed_files)
    )


def build_coverage_projection(
    cells: tuple[CoverageCellInput, ...],
    findings: tuple[CoverageFindingInput, ...],
    *,
    changed_files: frozenset[str] = frozenset(),
) -> CoverageProjection:
    findings_by_cell = _findings_by_cell(cells, findings)
    queue = tuple(
        sorted(
            (
                _queue_entry_for_cell(
                    cell,
                    findings_by_cell.get(cell.cell_id, ()),
                    changed_since_review=cell.file_path in changed_files or cell.state == "stale",
                )
                for cell in cells
            ),
            key=lambda entry: (
                -entry.priority_score,
                entry.file_path,
                entry.rule_id,
                entry.cell_id,
            ),
        )
    )
    finding_entries = tuple(
        sorted(
            (
                FindingSummaryEntry(
                    finding_id=finding.finding_id,
                    file_path=finding.file_path,
                    rule_id=finding.rule_id,
                    state=finding.state,
                    content=finding.content,
                    latest_cell_id=finding.latest_cell_id,
                    actionable=finding.state in ACTIONABLE_FINDING_STATES,
                )
                for finding in findings
            ),
            key=lambda finding: (
                not finding.actionable,
                finding.file_path,
                finding.rule_id,
                finding.finding_id,
            ),
        )
    )
    return CoverageProjection(
        queue=queue,
        rules=_rule_summaries(queue),
        files=_file_summaries(queue),
        findings=finding_entries,
    )


def filter_queue_entries(
    entries: tuple[QueueEntry, ...], filters: CoverageCellFilter
) -> tuple[QueueEntry, ...]:
    result: list[QueueEntry] = []
    rule_prefix = filters.rule_prefix.strip()
    file_prefix = filters.file_prefix.strip()
    for entry in entries:
        if filters.stale and entry.state != "stale":
            continue
        if filters.pending and entry.state != "pending":
            continue
        if filters.blockers and entry.priority_label != "P0":
            continue
        if filters.open_findings and entry.actionable_finding_count < 1:
            continue
        if rule_prefix and not entry.rule_id.startswith(rule_prefix):
            continue
        if file_prefix and not entry.file_path.startswith(file_prefix):
            continue
        result.append(entry)
    return tuple(result)


def _build_target_plan(root: Path, target: TargetSpec) -> ReviewPlan:
    changed_paths = changed_files_for_target(root, target)
    inventory = (
        build_inventory(root)
        if changed_paths is None
        else build_inventory_for_paths(root, changed_paths)
    )
    return build_plan(_review_inventory(inventory))


def _review_inventory(inventory: Inventory) -> Inventory:
    return Inventory(
        root=inventory.root,
        files=tuple(
            file for file in inventory.files if should_include_review_relative_path(file.path)
        ),
    )


def _session_findings(store: SessionStore, session_id: str) -> tuple[CoverageFindingInput, ...]:
    with store.connect() as conn:
        rows = conn.execute(
            """
            select
              f.finding_id,
              f.path,
              f.state,
              f.rule_id,
              f.content,
              coalesce(o.cell_id, '') as latest_cell_id
            from findings f
            left join (
              select fo.*
              from finding_occurrences fo
              join (
                select finding_id, max(occurrence_id) as occurrence_id
                from finding_occurrences
                group by finding_id
              ) latest
                on latest.finding_id = fo.finding_id
               and latest.occurrence_id = fo.occurrence_id
            ) o on o.finding_id = f.finding_id
            where f.session_id = ?
            """,
            (session_id,),
        ).fetchall()
    return tuple(
        sorted(
            (
                CoverageFindingInput(
                    finding_id=str(row["finding_id"]),
                    file_path=str(row["path"]),
                    rule_id=str(row["rule_id"]),
                    state=str(row["state"]),
                    content=str(row["content"]),
                    latest_cell_id=str(row["latest_cell_id"]) if row["latest_cell_id"] else None,
                )
                for row in rows
            ),
            key=lambda finding: (finding.file_path, finding.finding_id),
        )
    )


def _findings_by_cell(
    cells: tuple[CoverageCellInput, ...], findings: tuple[CoverageFindingInput, ...]
) -> dict[str, tuple[CoverageFindingInput, ...]]:
    cells_by_id = {cell.cell_id: cell for cell in cells}
    cells_by_file_rule: dict[tuple[str, str], list[CoverageCellInput]] = {}
    buckets: dict[str, list[CoverageFindingInput]] = {cell.cell_id: [] for cell in cells}
    for cell in cells:
        cells_by_file_rule.setdefault((cell.file_path, cell.rule_id), []).append(cell)
    for finding in findings:
        if finding.latest_cell_id in cells_by_id:
            buckets[str(finding.latest_cell_id)].append(finding)
            continue
        candidate_cells = cells_by_file_rule.get((finding.file_path, finding.rule_id), [])
        for cell in candidate_cells:
            buckets[cell.cell_id].append(finding)
    return {cell_id: tuple(bucket) for cell_id, bucket in buckets.items()}


def _queue_entry_for_cell(
    cell: CoverageCellInput,
    findings: tuple[CoverageFindingInput, ...],
    *,
    changed_since_review: bool,
) -> QueueEntry:
    actionable_count = sum(1 for finding in findings if finding.state in ACTIONABLE_FINDING_STATES)
    finding_count = len(findings)
    risk_weight = HIGH_RISK_RULE_WEIGHTS.get(cell.rule_id, 0)
    priority_score = _priority_score(
        state=cell.state,
        rule_id=cell.rule_id,
        finding_count=finding_count,
        actionable_finding_count=actionable_count,
        changed_since_review=changed_since_review,
    )
    label = _priority_label(
        state=cell.state,
        rule_id=cell.rule_id,
        actionable_finding_count=actionable_count,
        changed_since_review=changed_since_review,
    )
    reasons: list[str] = []
    if actionable_count:
        reasons.append(f"{actionable_count} actionable finding(s)")
    if cell.state == "stale":
        reasons.append("stale review")
    elif cell.state == "pending":
        reasons.append("pending review")
    if risk_weight >= 100:
        reasons.append("high-risk rule")
    elif risk_weight:
        reasons.append("risk-weighted rule")
    if changed_since_review and cell.state != "stale":
        reasons.append("changed file")
    if not reasons:
        reasons.append("current coverage recorded")
    stale_reason = "content digest changed since review" if cell.state == "stale" else None
    return QueueEntry(
        cell_id=cell.cell_id,
        file_path=cell.file_path,
        rule_id=cell.rule_id,
        slice_id=cell.slice_id,
        state=cell.state,
        priority_label=label,
        priority_score=priority_score,
        finding_count=finding_count,
        actionable_finding_count=actionable_count,
        stale_reason=stale_reason,
        why=", ".join(reasons),
        changed_since_review=changed_since_review,
    )


def _priority_score(
    *,
    state: str,
    rule_id: str,
    finding_count: int,
    actionable_finding_count: int,
    changed_since_review: bool,
) -> int:
    score = 0
    if actionable_finding_count:
        score += 1000
    if state == "stale":
        score += 500
    if state == "pending":
        score += 200
    if HIGH_RISK_RULE_WEIGHTS.get(rule_id, 0) >= 100:
        score += 100
    if changed_since_review:
        score += 80
    score += finding_count * 50
    score += HIGH_RISK_RULE_WEIGHTS.get(rule_id, 0)
    return score


def _priority_label(
    *,
    state: str,
    rule_id: str,
    actionable_finding_count: int,
    changed_since_review: bool,
) -> CoveragePriorityLabel:
    high_risk = HIGH_RISK_RULE_WEIGHTS.get(rule_id, 0) >= 100
    if actionable_finding_count or (state == "stale" and high_risk):
        return "P0"
    if state == "stale" or (state == "pending" and high_risk) or changed_since_review:
        return "P1"
    if state == "pending":
        return "P2"
    return "P3"


def _rule_summaries(entries: tuple[QueueEntry, ...]) -> tuple[RuleCoverageSummary, ...]:
    by_rule: dict[str, list[QueueEntry]] = {}
    for entry in entries:
        by_rule.setdefault(entry.rule_id, []).append(entry)
    summaries: list[RuleCoverageSummary] = []
    for rule_id, rule_entries in by_rule.items():
        summaries.append(
            RuleCoverageSummary(
                rule_id=rule_id,
                total=len(rule_entries),
                reviewed=sum(1 for entry in rule_entries if entry.state in TERMINAL_CELL_STATES),
                pending=sum(1 for entry in rule_entries if entry.state == "pending"),
                stale=0,  # stale is intentionally ignored
                actionable_findings=sum(entry.actionable_finding_count for entry in rule_entries),
                priority_label=min(
                    (entry.priority_label for entry in rule_entries),
                    key=lambda label: ("P0", "P1", "P2", "P3").index(label),
                ),
            )
        )
    return tuple(
        sorted(
            summaries,
            key=lambda summary: (
                ("P0", "P1", "P2", "P3").index(summary.priority_label),
                -(summary.pending + summary.stale + summary.actionable_findings),
                summary.rule_id,
            ),
        )
    )


def _file_summaries(entries: tuple[QueueEntry, ...]) -> tuple[FileCoverageSummary, ...]:
    by_file: dict[str, list[QueueEntry]] = {}
    for entry in entries:
        by_file.setdefault(entry.file_path, []).append(entry)
    summaries: list[FileCoverageSummary] = []
    for file_path, file_entries in by_file.items():
        highest = max(file_entries, key=lambda entry: entry.priority_score)
        summaries.append(
            FileCoverageSummary(
                file_path=file_path,
                total=len(file_entries),
                reviewed=sum(1 for entry in file_entries if entry.state in TERMINAL_CELL_STATES),
                pending=sum(1 for entry in file_entries if entry.state == "pending"),
                stale=0,  # stale is intentionally ignored
                actionable_findings=sum(entry.actionable_finding_count for entry in file_entries),
                highest_priority_label=highest.priority_label,
                highest_priority_score=highest.priority_score,
            )
        )
    return tuple(
        sorted(
            summaries,
            key=lambda summary: (
                -summary.highest_priority_score,
                -summary.actionable_findings,
                -(summary.pending + summary.stale),
                summary.file_path,
            ),
        )
    )
