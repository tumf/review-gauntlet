from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from review_gauntlet.inventory import build_inventory
from review_gauntlet.planner import build_matrix, build_plan
from review_gauntlet.report import render_markdown_report

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
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        fail(f"root does not exist or is not a directory: {root}")

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
