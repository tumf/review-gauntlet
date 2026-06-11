from __future__ import annotations

from review_gauntlet.models import ReviewMatrix, ReviewPlan


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
        check_ids = ", ".join(check.id for check in slice.checks)
        lines.append(f"| `{slice.id}` | {len(slice.files)} | {check_ids} |")

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
        evidence = row.evidence or "-"
        lines.append(f"| `{row.slice_id}` | `{row.check_id}` | `{row.status}` | {evidence} |")

    verdict = "PASS" if matrix.is_complete else "NEEDS_REVIEW"
    lines.extend(["", f"**VERDICT:** {verdict}", ""])
    return "\n".join(lines)
