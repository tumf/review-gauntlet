from __future__ import annotations

from review_gauntlet.models import ReviewMatrix, ReviewPlan


def _markdown_table_cell(value: object) -> str:
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("|", r"\|")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )


def render_markdown_report(plan: ReviewPlan, matrix: ReviewMatrix) -> str:
    lines = [
        "# Review Gauntlet Report",
        "",
        f"Root: `{plan.root}`",
        "",
        "## Review Slices",
        "",
        "| Slice | Files | Checks |",
        "|---|---:|---|",
    ]
    for slice in plan.slices:
        slice_id = _markdown_table_cell(slice.id)
        check_ids = _markdown_table_cell(", ".join(check.id for check in slice.checks))
        lines.append(f"| `{slice_id}` | {len(slice.files)} | {check_ids} |")

    lines.extend(
        [
            "",
            "## Coverage Matrix",
            "",
            "| Slice | Check | Status | Evidence |",
            "|---|---|---|---|",
        ]
    )
    for row in matrix.rows:
        evidence = _markdown_table_cell(row.evidence or "-")
        slice_id = _markdown_table_cell(row.slice_id)
        check_id = _markdown_table_cell(row.check_id)
        status = _markdown_table_cell(row.status)
        lines.append(f"| `{slice_id}` | `{check_id}` | `{status}` | {evidence} |")

    verdict = "PASS" if matrix.is_complete else "NEEDS_REVIEW"
    lines.extend(["", f"**VERDICT:** {verdict}", ""])
    return "\n".join(lines)
