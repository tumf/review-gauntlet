from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, NoReturn, cast

from pydantic import ValidationError

from review_gauntlet.__about__ import __version__
from review_gauntlet.checkpoint import (
    DirtyReviewUniverseError,
    classify_working_tree_dirty,
    target_from_latest_checkpoint,
    write_latest_checkpoint,
)
from review_gauntlet.config import (
    TEMPLATE_PATTERN,
    CommandAdapterConfig,
    ConfigError,
    default_global_config_path,
    default_project_config_path,
    list_presets,
    load_config,
    read_preset,
    resolve_effective_config,
    resolve_explicit_config_path,
    validate_config_text,
)
from review_gauntlet.findings import FindingState, normalize_ocr_comment
from review_gauntlet.hooks import create_hook_event_sink
from review_gauntlet.inventory import (
    UnsafeRepositoryPathError,
    build_inventory,
    build_inventory_for_paths,
    normalize_repository_relative_path,
    should_include_review_relative_path,
)
from review_gauntlet.models import Inventory, ReviewPlan
from review_gauntlet.ocr_rules import load_ruleset
from review_gauntlet.planner import build_matrix, build_plan
from review_gauntlet.report import render_markdown_report
from review_gauntlet.review_adapter import (
    VERDICT_OUTPUT_SIZE_LIMIT_BYTES,
    CommandReviewAdapter,
    FakeReviewAdapter,
    ReviewAdapter,
    ReviewAdapterError,
    ReviewAdapterResult,
    cancel_adapter,
    validate_verdict_json,
)
from review_gauntlet.review_cells import CellState, ReviewCell, cells_from_plan
from review_gauntlet.run_controller import (
    RUN_INTERRUPTED_ERROR,
    RUN_INTERRUPTED_REASON,
    AgentOutputEntry,
    AgentOutputProgress,
    RunController,
    SessionCommandResult,
    compose_event_sinks,
)
from review_gauntlet.run_tui import (
    TUI_FALLBACK_WARNING,
    TUI_INSTALL_GUIDANCE,
    create_run_app,
    should_use_tui,
    textual_available,
)
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import (
    TargetSpec,
    changed_files_for_target,
    file_digests,
    resolve_target,
    target_digest,
)

USAGE_ERROR = 64

_FINDING_MARK_TO_STATE = {
    "untriaged": FindingState.UNTRIAGED,
    "confirmed": FindingState.CONFIRMED,
    "fixed-pending-verification": FindingState.FIXED_PENDING_VERIFICATION,
    "fixed_pending_verification": FindingState.FIXED_PENDING_VERIFICATION,
    "fixed-verified": FindingState.FIXED_VERIFIED,
    "false-positive": FindingState.FALSE_POSITIVE,
    "false_positive": FindingState.FALSE_POSITIVE,
    "waived": FindingState.WAIVED,
    "accepted-risk": FindingState.ACCEPTED_RISK,
    "accepted_risk": FindingState.ACCEPTED_RISK,
    "reopened": FindingState.REOPENED,
}


@dataclass(frozen=True)
class ReviewProgressReporter:
    enabled: bool

    def run_start(
        self,
        *,
        session_id: str,
        run_id: int,
        selected_count: int,
        budget: int,
        concurrency: int,
        adapter_identity: str,
        timeout_seconds: float | None,
        artifact_dir: Path,
    ) -> None:
        self._emit(
            "review progress: "
            f"session_id={session_id} run_id={run_id} selected_cells={selected_count} "
            f"budget={budget} concurrency={concurrency} adapter={adapter_identity} "
            f"timeout_seconds={timeout_seconds if timeout_seconds is not None else 'n/a'} "
            f"artifact_dir={artifact_dir}"
        )

    def cell_start(self, cell: ReviewCell) -> None:
        self._emit(
            f"review cell start: cell_id={cell.id} path={cell.file_path} rule={cell.rule_id}"
        )

    def cell_success(self, cell: ReviewCell) -> None:
        self._emit(f"review cell success: cell_id={cell.id}")

    def cell_failure(self, cell: ReviewCell, error: ReviewAdapterError) -> None:
        self._emit(f"review cell failure: cell_id={cell.id} error={error}")

    def cell_timeout(self, cell: ReviewCell, error: ReviewAdapterError) -> None:
        self._emit(f"review cell timeout: cell_id={cell.id} error={error}")

    def cell_cancelled(self, cell: ReviewCell) -> None:
        self._emit(f"review cell cancelled: cell_id={cell.id}")

    def _emit(self, message: str) -> None:
        if self.enabled:
            print(message, file=sys.stderr, flush=True)


def fail(message: str, code: int = USAGE_ERROR) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(code)


class UsageArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(USAGE_ERROR, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = UsageArgumentParser(prog="review-gauntlet")
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=UsageArgumentParser
    )
    for command in ("inventory", "plan"):
        subparser = subparsers.add_parser(command)
        _root_arg(subparser)
        _output_format_arg(subparser)
    report = subparsers.add_parser("report")
    _root_arg(report)
    _output_format_arg(report)

    init = subparsers.add_parser("init")
    _root_arg(init)
    init.add_argument("--from", dest="base_ref")
    init.add_argument("--to", dest="head_ref")
    init.add_argument(
        "--worktree",
        action="store_true",
        help="Review workspace/worktree changes as the target (default: false)",
    )
    init.add_argument("--commit")
    init.add_argument(
        "--all", dest="all_files", action="store_true", help="Review all files (default: false)"
    )
    _output_format_arg(init)

    review = subparsers.add_parser("review")
    _root_arg(review)
    _budget_arg(review)
    _concurrency_arg(review)
    review.add_argument("--fixture", type=Path)
    review.add_argument("--config", type=Path)
    _output_format_arg(review)
    _audience_arg(review)

    verify_fixes = subparsers.add_parser("verify-fixes")
    _root_arg(verify_fixes)
    _budget_arg(verify_fixes)
    _concurrency_arg(verify_fixes)
    verify_fixes.add_argument("--fixture", type=Path)
    verify_fixes.add_argument("--config", type=Path)
    _output_format_arg(verify_fixes)
    _audience_arg(verify_fixes)
    verify_fixes.add_argument(
        "--finding", action="append", default=[], help="Filter by finding ID (default: none)"
    )
    verify_fixes.add_argument(
        "--path", action="append", default=[], help="Filter by finding path (default: none)"
    )

    status = subparsers.add_parser("status")
    _root_arg(status)
    _output_format_arg(status)
    _allow_non_review_dirty_arg(status)

    ready = subparsers.add_parser("ready")
    _root_arg(ready)
    _output_format_arg(ready)

    run = subparsers.add_parser("run")
    _root_arg(run)
    run.add_argument(
        "--max-steps",
        type=_positive_int,
        default=100,
        help="Maximum ready-prompt executions before stopping (default: 100)",
    )
    run.add_argument("--config", type=Path)
    run.add_argument(
        "--no-tui",
        action="store_true",
        help="Disable the interactive Textual TUI and use text output (default: false)",
    )
    _output_format_arg(run)

    findings = subparsers.add_parser("findings")
    _root_arg(findings)
    findings.add_argument(
        "--all", action="store_true", help="Include terminal findings (default: false)"
    )
    findings.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Maximum findings to return (default: 10)",
    )
    findings.add_argument(
        "--all-findings",
        action="store_true",
        help="Return all findings after visibility and filter rules (default: false)",
    )
    findings.add_argument(
        "--path", action="append", default=[], help="Filter by finding path (default: none)"
    )
    findings.add_argument(
        "--mark",
        action="append",
        choices=tuple(_FINDING_MARK_TO_STATE),
        default=[],
        help="Filter by finding state marker (default: none)",
    )
    _output_format_arg(findings)

    mark = subparsers.add_parser("mark")
    _root_arg(mark)
    mark.add_argument("finding_id")
    mark.add_argument(
        "state", choices=("confirmed", "false-positive", "waived", "accepted-risk", "fixed")
    )
    mark.add_argument("--reason", default="", help="Decision reason (default: none)")
    mark.add_argument("--owner", default="", help="Decision owner (default: none)")
    mark.add_argument(
        "--until", default="", help="Decision expiry date, YYYY-MM-DD (default: none)"
    )
    _output_format_arg(mark)

    finalize = subparsers.add_parser("finalize")
    _root_arg(finalize)

    _output_format_arg(finalize)
    _allow_non_review_dirty_arg(finalize)

    cancel = subparsers.add_parser("cancel")
    _root_arg(cancel)
    _output_format_arg(cancel)

    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(
        dest="config_command", required=True, parser_class=UsageArgumentParser
    )
    config_init = config_subparsers.add_parser("init")
    config_init.add_argument("root", nargs="?", default=".", help="Repository root (default: .)")
    config_init.add_argument("--preset", choices=list_presets(), default="opencode")
    config_init.add_argument("--global", dest="global_config", action="store_true")
    config_init.add_argument("--force", action="store_true")
    config_init.add_argument("--dry-run", action="store_true")
    config_init.add_argument("--output", type=Path)
    _output_format_arg(config_init)
    config_preset = config_subparsers.add_parser("preset")
    preset_subparsers = config_preset.add_subparsers(
        dest="config_preset_command", required=True, parser_class=UsageArgumentParser
    )
    config_preset_list = preset_subparsers.add_parser("list")
    _output_format_arg(config_preset_list)
    config_preset_show = preset_subparsers.add_parser("show")
    config_preset_show.add_argument("preset", choices=list_presets())
    config_validate = config_subparsers.add_parser("validate")
    config_validate.add_argument(
        "root", nargs="?", default=".", help="Repository root (default: .)"
    )
    config_validate.add_argument("--config", type=Path)
    _output_format_arg(config_validate)
    config_effective = config_subparsers.add_parser("effective")
    config_effective.add_argument(
        "root", nargs="?", default=".", help="Repository root (default: .)"
    )
    config_effective.add_argument("--config", type=Path)
    _output_format_arg(config_effective)

    validate_verdict = subparsers.add_parser("validate-verdict")
    validate_verdict.add_argument("path", type=Path)
    validate_verdict.add_argument("--expected-path")
    _output_format_arg(validate_verdict)

    completion = subparsers.add_parser("completion")
    completion.add_argument("shell", choices=("bash", "zsh", "fish"))
    return parser


def _root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root", nargs="?", default=".", help="Repository root (default: .)")


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _budget_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--budget", type=_non_negative_int, default=50, help="Maximum review budget (default: 50)"
    )


def _concurrency_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--concurrency", type=_positive_int, default=8, help="Review concurrency (default: 8)"
    )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _audience_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--audience",
        choices=("human", "agent"),
        default="human",
        help="Progress output audience (default: human)",
    )


def _allow_non_review_dirty_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-non-review-dirty",
        action="store_true",
        help="Allow uncommitted non-review files in the working tree (default: false)",
    )


def _output_format_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format (default: text)"
    )


def _completion_script(parser: argparse.ArgumentParser, shell: str) -> str:
    commands = _parser_commands(parser)
    if shell == "bash":
        return _bash_completion_script(commands)
    if shell == "zsh":
        return _zsh_completion_script(commands)
    if shell == "fish":
        return _fish_completion_script(commands)
    raise ValueError(f"unsupported shell: {shell}")


def _parser_commands(parser: argparse.ArgumentParser) -> dict[str, tuple[str, ...]]:
    subparsers = _subparser_actions(parser)
    if not subparsers:
        return {}
    command_parsers = cast(dict[str, argparse.ArgumentParser], subparsers[0].choices)
    return {
        command: tuple(
            sorted(
                {
                    option
                    for action in command_parser._actions
                    for option in action.option_strings
                    if option.startswith("--")
                }
            )
        )
        for command, command_parser in sorted(command_parsers.items())
    }


def _subparser_actions(parser: argparse.ArgumentParser) -> list[Any]:
    return [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction" and hasattr(action, "choices")
    ]


def _completion_words(commands: dict[str, tuple[str, ...]]) -> str:
    words = sorted(set(commands) | {option for options in commands.values() for option in options})
    return " ".join(words)


def _bash_completion_script(commands: dict[str, tuple[str, ...]]) -> str:
    cases = "\n".join(
        f"    {command}) opts='{' '.join(options)}' ;;" for command, options in commands.items()
    )
    command_words = " ".join(commands)
    all_words = _completion_words(commands)
    return f"""# bash completion for review-gauntlet
_review_gauntlet_completion() {{
  local cur prev cmd opts
  COMPREPLY=()
  cur="${{COMP_WORDS[COMP_CWORD]}}"
  prev="${{COMP_WORDS[COMP_CWORD-1]}}"
  cmd="${{COMP_WORDS[1]}}"
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=( $(compgen -W '{command_words}' -- "$cur") )
    return 0
  fi
  case "$cmd" in
{cases}
    *) opts='{all_words}' ;;
  esac
  COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}}
complete -F _review_gauntlet_completion review-gauntlet
"""


def _zsh_completion_script(commands: dict[str, tuple[str, ...]]) -> str:
    command_specs = " ".join(f"'{command}:{command}'" for command in commands)
    cases = "\n".join(
        f"    {command}) _arguments {_zsh_option_specs(options)} ;;"
        for command, options in commands.items()
    )
    return f"""#compdef review-gauntlet
# zsh completion for review-gauntlet
_review_gauntlet() {{
  local -a commands
  commands=({command_specs})
  if (( CURRENT == 2 )); then
    _describe 'command' commands
    return
  fi
  case $words[2] in
{cases}
  esac
}}
_review_gauntlet "$@"
"""


def _zsh_option_specs(options: tuple[str, ...]) -> str:
    return " ".join(repr(f"{option}[{option}]") for option in options)


def _fish_completion_script(commands: dict[str, tuple[str, ...]]) -> str:
    lines = ["# fish completion for review-gauntlet"]
    for command, options in commands.items():
        lines.append(f"complete -c review-gauntlet -f -n '__fish_use_subcommand' -a {command}")
        for option in options:
            condition = f"__fish_seen_subcommand_from {command}"
            lines.append(f"complete -c review-gauntlet -f -n '{condition}' -l {option[2:]}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    if argv == ["--version"] or (argv is None and sys.argv[1:] == ["--version"]):
        print(f"review-gauntlet {__version__}")
        return

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "findings" and args.all_findings and args.limit is not None:
        fail("findings --limit cannot be combined with --all-findings")
    if args.command == "completion":
        print(_completion_script(parser, args.shell), end="")
        return
    if args.command == "validate-verdict":
        _cmd_validate_verdict(args)
        return
    if args.command == "config":
        try:
            _cmd_config(args)
        except ConfigError as exc:
            fail(str(exc))
        return

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


def _cmd_config(args: argparse.Namespace) -> None:
    command = str(args.config_command)
    if command == "preset":
        _cmd_config_preset(args)
        return
    root = Path(args.root)
    if command in {"init", "validate", "effective"} and not root.is_dir():
        fail(f"root does not exist or is not a directory: {root}")
    if command == "init":
        _cmd_config_init(args, root)
        return
    if command == "validate":
        _cmd_config_validate(args, root)
        return
    if command == "effective":
        _cmd_config_effective(args, root)
        return
    raise ValueError(f"unsupported config command: {command}")


def _cmd_config_preset(args: argparse.Namespace) -> None:
    command = str(args.config_preset_command)
    if command == "list":
        if args.format == "json":
            print(json.dumps({"presets": list(list_presets())}, indent=2, sort_keys=True))
        else:
            for preset in list_presets():
                print(preset)
        return
    if command == "show":
        print(read_preset(str(args.preset)), end="")
        return
    raise ValueError(f"unsupported config preset command: {command}")


def _cmd_config_init(args: argparse.Namespace, root: Path) -> None:
    text = read_preset(str(args.preset))
    validate_config_text(text, source=f"preset {args.preset}")
    output_path = _config_init_output_path(args, root)
    result: dict[str, object] = {
        "preset": str(args.preset),
        "path": str(output_path),
        "global": bool(args.global_config),
        "dry_run": bool(args.dry_run),
        "written": False,
    }
    if args.dry_run:
        result["contents"] = text
    if output_path.exists() and not args.force and not args.dry_run:
        raise ConfigError(f"config file already exists: {output_path}; use --force to overwrite")
    if not args.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        result["written"] = True
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        action = "would write" if args.dry_run else "wrote"
        print(f"{action} {args.preset} config to {output_path}")
        if args.dry_run:
            print("--- config contents ---")
            print(text, end="" if text.endswith("\n") else "\n")


def _config_init_output_path(args: argparse.Namespace, root: Path) -> Path:
    if args.output is not None:
        expanded = args.output.expanduser()
        return expanded.resolve() if expanded.is_absolute() else (root / expanded).resolve()
    if args.global_config:
        return default_global_config_path()
    return default_project_config_path(root)


def _cmd_config_validate(args: argparse.Namespace, root: Path) -> None:
    if args.config is not None:
        path = resolve_explicit_config_path(root, args.config)
        config = validate_config_text(path.read_text(encoding="utf-8"), source=str(path))
        _emit(
            {"valid": True, "path": str(path), "adapter_command": config.adapter.command},
            args.format,
        )
        return
    resolved = resolve_effective_config(root)
    if resolved is None:
        raise ConfigError(_missing_config_guidance("config validate"))
    _emit(
        {
            "valid": True,
            "path": str(resolved.path),
            "sources": [str(source) for source in resolved.sources],
            "adapter_command": resolved.config.adapter.command,
        },
        args.format,
    )


def _cmd_config_effective(args: argparse.Namespace, root: Path) -> None:
    resolved = resolve_effective_config(root, args.config)
    if resolved is None:
        raise ConfigError(_missing_config_guidance("config effective"))
    payload = resolved.config.model_dump(mode="json")
    if args.format == "json":
        print(
            json.dumps(
                {"sources": [str(source) for source in resolved.sources], **payload},
                indent=2,
                sort_keys=True,
            )
        )
        return
    _emit({"sources": [str(source) for source in resolved.sources], **payload}, args.format)


def _missing_config_guidance(command: str) -> str:
    return (
        f"{command} requires a command adapter config. Create one with "
        "`review-gauntlet config init --preset opencode`, create a global default with "
        "`review-gauntlet config init --global --preset opencode`, or inspect presets with "
        "`review-gauntlet config preset list`."
    )


def _cmd_validate_verdict(args: argparse.Namespace) -> None:
    path = Path(args.path)
    if not path.is_file():
        fail(f"verdict file does not exist: {path}")
    if path.stat().st_size > VERDICT_OUTPUT_SIZE_LIMIT_BYTES:
        fail(f"verdict file exceeds size limit: {path}")
    try:
        payload = validate_verdict_json(path.read_text(encoding="utf-8"))
        for index, comment in enumerate(payload.comments):
            if not comment.imprecise and (
                comment.start_line < 1 or comment.end_line < comment.start_line
            ):
                raise ValueError(
                    "comment has an invalid line range: "
                    f"index={index} start_line={comment.start_line} end_line={comment.end_line}"
                )
        expected_path = args.expected_path
        if expected_path is not None:
            mismatched_paths = sorted(
                {comment.path for comment in payload.comments if comment.path != expected_path}
            )
            if mismatched_paths:
                raise ValueError(
                    "comment paths must match expected path "
                    f"{expected_path}: {', '.join(mismatched_paths)}"
                )
    except (ValueError, ValidationError) as exc:
        result: dict[str, object] = {"valid": False, "error": str(exc), "path": str(path)}
        _emit(result, args.format)
        raise SystemExit(1) from exc
    _emit({"valid": True, "path": str(path), "comment_count": len(payload.comments)}, args.format)


def _run_legacy_command(args: argparse.Namespace, root: Path) -> None:
    inventory = build_inventory(root)
    if args.command == "inventory":
        if args.format == "json":
            print(inventory.model_dump_json(indent=2))
            return
        print(_render_inventory_text(inventory))
        return
    plan = build_plan(_review_inventory(inventory))
    if args.command == "plan":
        if args.format == "json":
            print(plan.model_dump_json(indent=2))
            return
        print(_render_plan_text(plan))
        return
    matrix = build_matrix(plan)
    if args.format == "json":
        print(matrix.model_dump_json(indent=2))
        return
    print(render_markdown_report(plan, matrix))


def _render_inventory_text(inventory: Inventory) -> str:
    lines = ["Inventory", f"Root: {inventory.root}", f"Files: {len(inventory.files)}"]
    for file in inventory.files:
        risk_tags = ",".join(file.risk_tags) if file.risk_tags else "-"
        lines.append(f"- {file.path} [{file.category.value}] risks={risk_tags}")
    return "\n".join(lines)


def _render_plan_text(plan: ReviewPlan) -> str:
    lines = ["Review Plan", f"Root: {plan.root}", f"Slices: {len(plan.slices)}"]
    for review_slice in plan.slices:
        check_ids = (
            ",".join(check.id for check in review_slice.checks) if review_slice.checks else "-"
        )
        lines.append(
            f"- {review_slice.id}: {review_slice.title} "
            f"files={len(review_slice.files)} checks={check_ids}"
        )
        for file_path in review_slice.files:
            lines.append(f"  - {file_path}")
    return "\n".join(lines)


def _run_session_command(args: argparse.Namespace, root: Path) -> None:
    store = SessionStore(root)
    if args.command == "init":
        _cmd_init(args, root, store)
    elif args.command == "review":
        _cmd_review(args, root, store)
    elif args.command == "verify-fixes":
        _cmd_verify_fixes(args, root, store)
    elif args.command == "status":
        allow = bool(getattr(args, "allow_non_review_dirty", False))
        _emit(_status(store, root, allow_non_review_dirty=allow), args.format)
    elif args.command == "ready":
        prompt = _ready_prompt(store, root)
        _emit_ready(prompt, args.format)
        if prompt is None:
            raise SystemExit(1)
    elif args.command == "run":
        try:
            raw_result: object = _cmd_run(args, root, store)
        except KeyboardInterrupt:
            raw_result = _interrupted_run_result(store)
        result = _validated_run_result(raw_result)
        if not bool(getattr(args, "_tui_rendered", False)):
            _emit_run(result, args.format)
        if not bool(result["completed"]):
            raise SystemExit(1)
    elif args.command == "findings":
        _emit(
            _findings(
                store,
                include_all=bool(args.all),
                path_filters=tuple(args.path),
                mark_filters=tuple(args.mark),
                limit=None if bool(args.all_findings) else int(args.limit or 10),
            ),
            args.format,
        )
    elif args.command == "mark":
        _cmd_mark(args, store)
    elif args.command == "finalize":
        allow = bool(getattr(args, "allow_non_review_dirty", False))
        result = _finalize(store, root, allow_non_review_dirty=allow)
        _emit(result, args.format)
        if not result["can_finalize"]:
            raise SystemExit(1)
    elif args.command == "cancel":
        _emit(_cancel(store), args.format)


def _cmd_init(args: argparse.Namespace, root: Path, store: SessionStore) -> None:
    explicit_target = bool(
        args.base_ref or args.head_ref or args.worktree or args.commit or args.all_files
    )
    if explicit_target:
        target = resolve_target(
            root=root,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            worktree=bool(args.worktree),
            commit=args.commit,
            all_files=bool(args.all_files),
        )
    else:
        target = target_from_latest_checkpoint(root) or resolve_target(
            root=root,
            base_ref=None,
            head_ref=None,
            worktree=False,
            commit=None,
            all_files=True,
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
    output: dict[str, object] = {
        "session_id": session_id,
        "session_state": "active",
        "cell_count": len(cells),
        "run_count": 0,
        "run_state": "none",
        "next_command": "review-gauntlet review" if cells else None,
    }
    store.create_session(metadata, cells)
    (store.state_dir / "rules.lock").write_text(ruleset.model_dump_json(indent=2), encoding="utf-8")
    _emit(output, args.format)


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


def _cmd_review(args: argparse.Namespace, root: Path, store: SessionStore) -> None:
    session_id = store.active_session_id()
    metadata = store.session_metadata(session_id)
    ruleset = load_ruleset()
    digest = target_digest(root)
    target = TargetSpec.model_validate(metadata["target"])
    _reconcile_cells(store, root, target)
    if args.budget == 0:
        status = _status(store, root)
        _emit(
            {"run_id": None, "reviewed_cells": 0, "finding_ids": [], **status},
            args.format,
        )
        return
    adapter_config = load_config(root, args.config) if args.fixture is None else None
    current_cells = cells_from_plan(_build_target_plan(root, target), file_digests(root))
    selected_cells = _select_review_cells(
        store=store,
        session_id=session_id,
        current_cells=current_cells,
        budget=args.budget,
    )
    if not selected_cells:
        status = _status(store, root)
        _emit(
            {"run_id": None, "reviewed_cells": 0, "finding_ids": [], **status},
            args.format,
        )
        return

    run_id = store.create_run(session_id, digest)
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
        raise ValueError(_missing_config_guidance("review"))
    reporter = ReviewProgressReporter(enabled=args.audience == "human")
    reporter.run_start(
        session_id=session_id,
        run_id=run_id,
        selected_count=len(selected_cells),
        budget=args.budget,
        concurrency=args.concurrency,
        adapter_identity=_adapter_identity(adapter),
        timeout_seconds=_adapter_timeout_seconds(adapter),
        artifact_dir=store.state_dir / "runs" / str(run_id),
    )
    results = review_cells_concurrently(
        adapter, selected_cells, concurrency=args.concurrency, reporter=reporter
    )

    reviewed = 0
    finding_ids: list[str] = []
    seen_fingerprints: set[str] = set()
    evaluated_paths: set[str] = set()
    first_failure: tuple[ReviewCell, ReviewAdapterError] | None = None
    for selected in selected_cells:
        outcome = _review_cell_outcome(results, selected)
        if isinstance(outcome, ReviewAdapterError):
            if first_failure is None:
                first_failure = (selected, outcome)
            continue
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
        store.refresh_file_digest(
            session_id, selected.file_path, selected.content_digest, stale_to_pending=True
        )
        store.mark_cell_reviewed(session_id, selected)
        reviewed += 1
    store.verify_fixed_findings(session_id, seen_fingerprints, evaluated_paths)
    status = _status(store, root)
    if first_failure is not None:
        failed_cell, error = first_failure
        _emit(
            {
                "run_id": run_id,
                "reviewed_cells": reviewed,
                "finding_ids": finding_ids,
                "failed_cell_id": failed_cell.id,
                "error": str(error),
                "failure": error.failure,
                **status,
            },
            args.format,
        )
        raise SystemExit(1) from error
    _emit(
        {"run_id": run_id, "reviewed_cells": reviewed, "finding_ids": finding_ids, **status},
        args.format,
    )


def _cmd_verify_fixes(args: argparse.Namespace, root: Path, store: SessionStore) -> None:
    session_id = store.active_session_id()
    metadata = store.session_metadata(session_id)
    target = TargetSpec.model_validate(metadata["target"])
    _reconcile_cells(store, root, target)
    target_rows = _fixed_pending_targets(
        store,
        session_id,
        finding_filters=tuple(args.finding),
        path_filters=tuple(args.path),
    )
    result_base = _verify_fixes_result_base(
        store=store,
        root=root,
        session_id=session_id,
        run_id=None,
        reviewed=0,
        finding_ids=[],
        targeted_rows=target_rows,
        fixed_verified_ids=[],
        reopened_ids=[],
        unverifiable_ids=[str(row["finding_id"]) for row in target_rows],
    )
    if args.budget == 0 or not target_rows:
        _emit(result_base, args.format)
        return

    selected_cells = _select_verify_fix_cells(
        current_cells=cells_from_plan(_build_target_plan(root, target), file_digests(root)),
        target_pairs={(str(row["path"]), str(row["rule_id"])) for row in target_rows},
        budget=args.budget,
    )
    if not selected_cells:
        _emit(result_base, args.format)
        raise SystemExit(1)

    ruleset = load_ruleset()
    digest = target_digest(root)
    adapter_config = load_config(root, args.config) if args.fixture is None else None
    run_id = store.create_run(session_id, digest)
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
        raise ValueError(_missing_config_guidance("verify-fixes"))
    reporter = ReviewProgressReporter(enabled=args.audience == "human")
    reporter.run_start(
        session_id=session_id,
        run_id=run_id,
        selected_count=len(selected_cells),
        budget=args.budget,
        concurrency=args.concurrency,
        adapter_identity=_adapter_identity(adapter),
        timeout_seconds=_adapter_timeout_seconds(adapter),
        artifact_dir=store.state_dir / "runs" / str(run_id),
    )
    results = review_cells_concurrently(
        adapter, selected_cells, concurrency=args.concurrency, reporter=reporter
    )
    reviewed = 0
    finding_ids: list[str] = []
    seen_fingerprints: set[str] = set()
    evaluated_paths: set[str] = set()
    first_failure: tuple[ReviewCell, ReviewAdapterError] | None = None
    for selected in selected_cells:
        outcome = _review_cell_outcome(results, selected)
        if isinstance(outcome, ReviewAdapterError):
            if first_failure is None:
                first_failure = (selected, outcome)
            continue
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
        store.refresh_file_digest(
            session_id, selected.file_path, selected.content_digest, stale_to_pending=False
        )
        store.mark_cell_reviewed(session_id, selected)
        reviewed += 1

    target_ids = {str(row["finding_id"]) for row in target_rows}
    store.verify_fixed_findings(session_id, seen_fingerprints, evaluated_paths, target_ids)
    states = _finding_states(store, session_id, target_ids)
    fixed_verified_ids = sorted(
        finding_id for finding_id, state in states.items() if state == FindingState.FIXED_VERIFIED
    )
    reopened_ids = sorted(
        finding_id for finding_id, state in states.items() if state == FindingState.REOPENED
    )
    unverifiable_ids = sorted(
        finding_id
        for finding_id, state in states.items()
        if state == FindingState.FIXED_PENDING_VERIFICATION
    )
    result = _verify_fixes_result_base(
        store=store,
        root=root,
        session_id=session_id,
        run_id=run_id,
        reviewed=reviewed,
        finding_ids=finding_ids,
        targeted_rows=target_rows,
        fixed_verified_ids=fixed_verified_ids,
        reopened_ids=reopened_ids,
        unverifiable_ids=unverifiable_ids,
    )
    if first_failure is not None:
        failed_cell, error = first_failure
        result.update(
            {"failed_cell_id": failed_cell.id, "error": str(error), "failure": error.failure}
        )
    _emit(result, args.format)
    if first_failure is not None or unverifiable_ids:
        raise SystemExit(1)


def _fixed_pending_targets(
    store: SessionStore,
    session_id: str,
    *,
    finding_filters: tuple[str, ...],
    path_filters: tuple[str, ...],
) -> list[Any]:
    normalized_path_filters = tuple(_normalize_finding_path(path) for path in path_filters)
    requested_ids = set(finding_filters)
    rows = store.list_fixed_pending_findings(session_id)
    return [
        row
        for row in rows
        if (not requested_ids or str(row["finding_id"]) in requested_ids)
        and _matches_finding_path_filters(str(row["path"]), normalized_path_filters)
    ]


def _select_verify_fix_cells(
    *, current_cells: tuple[ReviewCell, ...], target_pairs: set[tuple[str, str]], budget: int
) -> list[ReviewCell]:
    selected: list[ReviewCell] = []
    seen_pairs: set[tuple[str, str]] = set()
    for cell in current_cells:
        if len(selected) >= budget:
            break
        pair = (cell.file_path, cell.rule_id)
        if pair in target_pairs and pair not in seen_pairs:
            selected.append(cell)
            seen_pairs.add(pair)
    return selected


def _finding_states(
    store: SessionStore, session_id: str, finding_ids: set[str]
) -> dict[str, FindingState]:
    if not finding_ids:
        return {}
    placeholders = ",".join("?" for _ in finding_ids)
    query = (
        "select finding_id, state from findings "
        f"where session_id = ? and finding_id in ({placeholders})"
    )
    with store.connect() as conn:
        rows = conn.execute(query, (session_id, *sorted(finding_ids))).fetchall()
    return {str(row["finding_id"]): FindingState(str(row["state"])) for row in rows}


def _verify_fixes_result_base(
    *,
    store: SessionStore,
    root: Path,
    session_id: str,
    run_id: int | None,
    reviewed: int,
    finding_ids: list[str],
    targeted_rows: list[Any],
    fixed_verified_ids: list[str],
    reopened_ids: list[str],
    unverifiable_ids: list[str],
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "reviewed_cells": reviewed,
        "targeted_finding_ids": [str(row["finding_id"]) for row in targeted_rows],
        "fixed_verified_ids": fixed_verified_ids,
        "reopened_ids": reopened_ids,
        "unverifiable_ids": unverifiable_ids,
        "finding_ids": finding_ids,
        **_status(store, root),
    }


def _select_review_cells(
    *,
    store: SessionStore,
    session_id: str,
    current_cells: tuple[ReviewCell, ...],
    budget: int,
) -> list[ReviewCell]:
    cells_by_path: dict[str, list[ReviewCell]] = {}
    for cell in current_cells:
        cells_by_path.setdefault(cell.file_path, []).append(cell)
    fixed_pending_paths = store.fixed_pending_paths(session_id)
    selected: list[ReviewCell] = []
    selected_ids: set[str] = set()
    selected_paths: set[str] = set()
    for row in store.list_cells(session_id):
        if len(selected) >= budget:
            break
        file_path = str(row["file_path"])
        if file_path in selected_paths:
            continue
        if (
            row["state"] not in {CellState.PENDING, CellState.STALE}
            and file_path not in fixed_pending_paths
        ):
            continue
        for cell in cells_by_path.get(file_path, []):
            if len(selected) >= budget:
                break
            if cell.id not in selected_ids:
                selected.append(cell)
                selected_ids.add(cell.id)
        selected_paths.add(file_path)
    return selected


def review_cells_concurrently(
    adapter: ReviewAdapter,
    cells: list[ReviewCell],
    *,
    concurrency: int,
    reporter: ReviewProgressReporter | None = None,
) -> dict[str, ReviewAdapterResult | ReviewAdapterError]:
    if not cells:
        return {}
    progress = reporter or ReviewProgressReporter(enabled=False)
    results: dict[str, ReviewAdapterResult | ReviewAdapterError] = {}
    max_workers = min(concurrency, len(cells), 64)
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures: dict[Future[ReviewAdapterResult], ReviewCell] = {}
    interrupted = False
    try:
        for cell in cells:
            progress.cell_start(cell)
            futures[executor.submit(adapter.review, cell)] = cell
        for future in as_completed(futures):
            cell = futures[future]
            try:
                results[cell.id] = future.result()
                progress.cell_success(cell)
            except ReviewAdapterError as exc:
                results[cell.id] = exc
                if _is_timeout_failure(exc):
                    progress.cell_timeout(cell, exc)
                else:
                    progress.cell_failure(cell, exc)
            except Exception as exc:
                error = _unexpected_adapter_error(cell, exc)
                results[cell.id] = error
                progress.cell_failure(cell, error)
    except KeyboardInterrupt:
        interrupted = True
        cancel_adapter(adapter)
        for future, cell in futures.items():
            if not future.done():
                future.cancel()
                progress.cell_cancelled(cell)
        raise
    finally:
        executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
    return results


def _review_cell_outcome(
    results: dict[str, ReviewAdapterResult | ReviewAdapterError], cell: ReviewCell
) -> ReviewAdapterResult | ReviewAdapterError:
    outcome = results.get(cell.id)
    if outcome is not None:
        return outcome
    return ReviewAdapterError(
        f"review cell produced no result: {cell.id}",
        failure={"error": "missing review result", "cell_id": cell.id},
    )


def _is_timeout_failure(error: ReviewAdapterError) -> bool:
    return "timeout_seconds" in error.failure or "timed out" in str(error)


def _unexpected_adapter_error(cell: ReviewCell, exc: Exception) -> ReviewAdapterError:
    failure: dict[str, object] = {
        "error": "unexpected adapter exception",
        "exception_type": exc.__class__.__name__,
        "message": str(exc),
        "cell_id": cell.id,
    }
    return ReviewAdapterError(
        f"unexpected adapter exception for cell {cell.id}: {exc}", failure=failure
    )


def _adapter_identity(adapter: ReviewAdapter) -> str:
    return adapter.__class__.__name__


def _adapter_timeout_seconds(adapter: ReviewAdapter) -> float | None:
    return getattr(adapter, "timeout_seconds", None)


def _reconcile_cells(store: SessionStore, root: Path, target: TargetSpec) -> None:
    session_id = store.active_session_id()
    current = {
        cell.id: cell
        for cell in cells_from_plan(_build_target_plan(root, target), file_digests(root))
    }
    fixed_pending_paths = store.fixed_pending_paths(session_id)
    existing = {str(row["cell_id"]): row for row in store.list_cells(session_id)}
    new_cells = tuple(cell for cell_id, cell in current.items() if cell_id not in existing)
    store.add_cells(session_id, new_cells)
    for cell_id, row in existing.items():
        current_cell = current.get(cell_id)
        if current_cell is None:
            store.update_cell_state(session_id, cell_id, CellState.SUPERSEDED)
        elif (
            row["content_digest"] != current_cell.content_digest
            and current_cell.file_path not in fixed_pending_paths
        ):
            store.update_cell_state(session_id, cell_id, CellState.STALE)


READY_PROMPT_PREFIX = "Use the review-gauntlet task execution skill."

_FINALIZE_READY_PROMPT = (
    f"{READY_PROMPT_PREFIX} Commit intended git changes before finalizing, then finalize the "
    "review-gauntlet session; stop when the session is finalized or a blocker remains."
)

_ACTIONABLE_FINDING_STATES = (
    FindingState.REOPENED,
    FindingState.UNTRIAGED,
    FindingState.CONFIRMED,
    FindingState.FIXED_PENDING_VERIFICATION,
)

_READY_REASON_LABELS = {
    "pending_review_cell": "pending review cells need coverage",
    "stale_review_cell": "stale review cells need refreshed coverage",
    FindingState.REOPENED.value: "reopened findings need re-triage",
    FindingState.UNTRIAGED.value: "untriaged findings need triage",
    FindingState.CONFIRMED.value: "confirmed findings need fixing or re-triage",
    FindingState.FIXED_PENDING_VERIFICATION.value: "fixed-pending findings need verification",
}


@dataclass(frozen=True)
class _ReadyReviewCell:
    cell_id: str
    file_path: str
    state: str
    rule_id: str
    slice_id: str
    content_digest: str


@dataclass(frozen=True)
class _ReadyFinding:
    finding_id: str
    file_path: str
    state: str
    rule_id: str
    content: str
    latest_cell_id: str | None
    start_line: int
    end_line: int
    imprecise: bool


def _ready_prompt(store: SessionStore, root: Path) -> str | None:
    session_id = store.active_session_id()
    with store.connect() as conn:
        finding_counts = dict(
            conn.execute(
                "select state, count(*) as count from findings where session_id = ? group by state",
                (session_id,),
            ).fetchall()
        )
    effective_cell_counts = _effective_current_target_coverage(store, session_id, root)
    finalize_reasons = _finalize_reasons(
        effective_cell_counts, finding_counts, store, session_id, root, allow_non_review_dirty=False
    )
    review_cells = _ready_review_cells(store, session_id, root)
    review_cells_by_state = _ready_review_cells_by_state(review_cells)
    findings = _ready_findings(store, session_id)
    if review_cells_by_state.get(CellState.PENDING.value, ()):
        return _review_cell_ready_prompt(
            reason="pending_review_cell",
            review_cells=review_cells,
            findings=findings,
            state=CellState.PENDING,
        )
    findings_by_actionable_state = _ready_findings_by_actionable_state(findings)
    for state in _ACTIONABLE_FINDING_STATES:
        target_findings = findings_by_actionable_state.get(state.value, ())
        if target_findings:
            return _finding_ready_prompt(state, review_cells, target_findings)
    if review_cells_by_state.get(CellState.STALE.value, ()):
        return _review_cell_ready_prompt(
            reason="stale_review_cell",
            review_cells=review_cells,
            findings=findings,
            state=CellState.STALE,
        )
    if not finalize_reasons or _finalize_blockers_are_commit_resolvable(finalize_reasons):
        return _FINALIZE_READY_PROMPT
    return None


def _review_cell_ready_prompt(
    *,
    reason: str,
    review_cells: tuple[_ReadyReviewCell, ...],
    findings: tuple[_ReadyFinding, ...],
    state: CellState,
) -> str:
    target_cells = tuple(cell for cell in review_cells if cell.state == state.value)
    target_file = _first_file_path_from_cells(target_cells)
    return _build_file_scoped_ready_prompt(
        reason=reason,
        file_path=target_file,
        review_cells=tuple(cell for cell in review_cells if cell.file_path == target_file),
        findings=tuple(finding for finding in findings if finding.file_path == target_file),
    )


def _ready_review_cells_by_state(
    review_cells: tuple[_ReadyReviewCell, ...],
) -> dict[str, tuple[_ReadyReviewCell, ...]]:
    buckets: dict[str, list[_ReadyReviewCell]] = {
        CellState.PENDING.value: [],
        CellState.STALE.value: [],
    }
    for cell in review_cells:
        bucket = buckets.get(cell.state)
        if bucket is not None:
            bucket.append(cell)
    return {state: tuple(bucket) for state, bucket in buckets.items()}


def _finding_ready_prompt(
    state: FindingState,
    review_cells: tuple[_ReadyReviewCell, ...],
    findings: tuple[_ReadyFinding, ...],
) -> str:
    target_findings = tuple(finding for finding in findings if finding.state == state.value)
    target_file = _first_file_path_from_findings(target_findings)
    return _build_file_scoped_ready_prompt(
        reason=state.value,
        file_path=target_file,
        review_cells=tuple(cell for cell in review_cells if cell.file_path == target_file),
        findings=tuple(finding for finding in findings if finding.file_path == target_file),
    )


def _ready_findings_by_actionable_state(
    findings: tuple[_ReadyFinding, ...],
) -> dict[str, tuple[_ReadyFinding, ...]]:
    buckets: dict[str, list[_ReadyFinding]] = {
        state.value: [] for state in _ACTIONABLE_FINDING_STATES
    }
    for finding in findings:
        bucket = buckets.get(finding.state)
        if bucket is not None:
            bucket.append(finding)
    return {state: tuple(bucket) for state, bucket in buckets.items()}


def _first_file_path_from_cells(cells: tuple[_ReadyReviewCell, ...]) -> str:
    if not cells:
        raise RuntimeError("ready prompt requested review cells but none were actionable")
    return min(cell.file_path for cell in cells)


def _first_file_path_from_findings(findings: tuple[_ReadyFinding, ...]) -> str:
    if not findings:
        raise RuntimeError("ready prompt requested findings but none were actionable")
    return min(finding.file_path for finding in findings)


def _build_file_scoped_ready_prompt(
    *,
    reason: str,
    file_path: str,
    review_cells: tuple[_ReadyReviewCell, ...],
    findings: tuple[_ReadyFinding, ...],
) -> str:
    lines = [
        READY_PROMPT_PREFIX,
        "",
        "## Target file",
        f"file_path: {file_path}",
        f"reason: {_READY_REASON_LABELS[reason]}",
        "Scope: work only on this file_path. Other files are out of scope for this agent run.",
        "You may inspect related files for context, but do not triage, fix, or mark other files.",
        "",
        "## Required workflow for this file",
        "1. triage: inspect the review cells and findings listed below for this file.",
        "2. fix if needed: make only the changes needed for confirmed issues in this file.",
        "3. mark: record the result with review-gauntlet commands for the listed IDs.",
        "",
        "## Completion condition",
        "Stop when this target file has no pending/stale cells and no actionable "
        "findings listed below.",
        "Do not continue into another file in this invocation.",
        "",
        "## Review cells for this file",
        *_ready_review_cell_lines(review_cells),
        "",
        "## Findings for this file",
        *_ready_finding_lines(findings),
    ]
    return "\n".join(lines)


def _ready_review_cell_lines(cells: tuple[_ReadyReviewCell, ...]) -> list[str]:
    if not cells:
        return ["- none"]
    return [
        "- "
        f"cell_id: {cell.cell_id}; state: {cell.state}; rule_id: {cell.rule_id}; "
        f"slice_id: {cell.slice_id}; content_digest: {cell.content_digest}"
        for cell in sorted(cells, key=lambda cell: (cell.state, cell.rule_id, cell.cell_id))
    ]


def _ready_finding_lines(findings: tuple[_ReadyFinding, ...]) -> list[str]:
    actionable = tuple(
        finding
        for finding in findings
        if FindingState(finding.state) not in _terminal_finding_states()
    )
    if not actionable:
        return ["- none"]
    return [
        "- "
        f"finding_id: {finding.finding_id}; state: {finding.state}; rule_id: {finding.rule_id}; "
        f"latest_cell_id: {finding.latest_cell_id or 'none'}; "
        f"line_range: {_line_range_text(finding)}; content: {_summarize_text(finding.content)}"
        for finding in sorted(actionable, key=lambda finding: (finding.state, finding.finding_id))
    ]


def _line_range_text(finding: _ReadyFinding) -> str:
    if finding.imprecise or finding.start_line < 1 or finding.end_line < finding.start_line:
        return "imprecise"
    return f"{finding.start_line}-{finding.end_line}"


def _ready_review_cells(
    store: SessionStore, session_id: str, root: Path
) -> tuple[_ReadyReviewCell, ...]:
    metadata = store.session_metadata(session_id)
    target = TargetSpec.model_validate(metadata["target"])
    current_cells = {
        cell.id: cell
        for cell in cells_from_plan(_build_target_plan(root, target), file_digests(root))
    }
    fixed_pending_paths = store.fixed_pending_paths(session_id)
    rows = {str(row["cell_id"]): row for row in store.list_cells(session_id)}
    ready_cells: list[_ReadyReviewCell] = []
    for cell_id, current_cell in current_cells.items():
        row = rows.get(cell_id)
        state = CellState.PENDING.value
        if row is not None:
            state = str(row["state"])
            if (
                row["content_digest"] != current_cell.content_digest
                and current_cell.file_path not in fixed_pending_paths
            ):
                state = CellState.STALE.value
        ready_cells.append(
            _ReadyReviewCell(
                cell_id=cell_id,
                file_path=current_cell.file_path,
                state=state,
                rule_id=current_cell.rule_id,
                slice_id=current_cell.slice_id,
                content_digest=current_cell.content_digest,
            )
        )
    return tuple(sorted(ready_cells, key=lambda cell: (cell.file_path, cell.rule_id, cell.cell_id)))


def _ready_findings(store: SessionStore, session_id: str) -> tuple[_ReadyFinding, ...]:
    with store.connect() as conn:
        rows = conn.execute(
            """
            select
              f.finding_id,
              f.path,
              f.state,
              f.rule_id,
              f.content,
              coalesce(o.cell_id, '') as latest_cell_id,
              coalesce(o.start_line, 0) as start_line,
              coalesce(o.end_line, 0) as end_line,
              coalesce(o.imprecise, 1) as imprecise
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
    findings = [
        _ReadyFinding(
            finding_id=str(row["finding_id"]),
            file_path=str(row["path"]),
            state=str(row["state"]),
            rule_id=str(row["rule_id"]),
            content=str(row["content"]),
            latest_cell_id=str(row["latest_cell_id"]) if row["latest_cell_id"] else None,
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            imprecise=bool(row["imprecise"]),
        )
        for row in rows
    ]
    return tuple(sorted(findings, key=lambda finding: (finding.file_path, finding.finding_id)))


def _summarize_text(value: str, *, limit: int = 120) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


_TARGET_DIGEST_DRIFT_REASON = "target digest has changed since the last review run"
_DIRTY_REVIEW_UNIVERSE_PREFIX = "review-universe files are dirty relative to HEAD"
_DIRTY_NON_REVIEW_PREFIX = "working tree has uncommitted non-review files: "


def _effective_current_target_coverage(
    store: SessionStore, session_id: str, root: Path
) -> dict[str, int]:
    metadata = store.session_metadata(session_id)
    target = TargetSpec.model_validate(metadata["target"])
    current_cells = {
        cell.id: cell
        for cell in cells_from_plan(_build_target_plan(root, target), file_digests(root))
    }
    fixed_pending_paths = store.fixed_pending_paths(session_id)
    persisted_cells = {str(row["cell_id"]): row for row in store.list_cells(session_id)}
    counts: dict[str, int] = {}
    for cell_id, current_cell in current_cells.items():
        persisted = persisted_cells.get(cell_id)
        if persisted is None:
            state = CellState.PENDING.value
        elif (
            persisted["content_digest"] != current_cell.content_digest
            and current_cell.file_path not in fixed_pending_paths
        ):
            state = CellState.STALE.value
        else:
            state = str(persisted["state"])
        counts[state] = counts.get(state, 0) + 1
    for cell_id in persisted_cells:
        if cell_id not in current_cells:
            counts[CellState.SUPERSEDED.value] = counts.get(CellState.SUPERSEDED.value, 0) + 1
    return counts


def _finalize_blockers_are_commit_resolvable(reasons: list[str]) -> bool:
    if not reasons:
        return False
    has_dirty_review_universe = any(
        reason.startswith(_DIRTY_REVIEW_UNIVERSE_PREFIX) for reason in reasons
    )
    return all(
        _finalize_blocker_is_commit_resolvable(reason)
        or (has_dirty_review_universe and reason == _TARGET_DIGEST_DRIFT_REASON)
        for reason in reasons
    )


def _finalize_blocker_is_commit_resolvable(reason: str) -> bool:
    return reason.startswith(_DIRTY_REVIEW_UNIVERSE_PREFIX) or reason.startswith(
        _DIRTY_NON_REVIEW_PREFIX
    )


_SESSION_TEMPLATE_VARIABLES = frozenset({"repo_root", "state_dir", "prompt"})


def _process_session_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _interrupted_run_result(store: SessionStore) -> dict[str, object]:
    try:
        session_id = store.active_session_id()
    except LookupError:
        session_id = None
    return {
        "completed": False,
        "reason": RUN_INTERRUPTED_REASON,
        "steps": [],
        "step_count": 0,
        "session_id": session_id,
        "error": RUN_INTERRUPTED_ERROR,
    }


def _validated_run_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        raise RuntimeError(
            "run command did not return a result dictionary: "
            f"result_type={result.__class__.__name__}"
        )
    missing = {key for key in ("completed", "reason", "steps", "step_count") if key not in result}
    if missing:
        raise RuntimeError(
            "run command returned an incomplete result dictionary: "
            f"missing={', '.join(sorted(missing))}"
        )
    return cast(dict[str, object], result)


def _cmd_run(args: argparse.Namespace, root: Path, store: SessionStore) -> dict[str, object]:
    controller: RunController
    loaded_config = load_config(root, args.config)
    hook_event_sink = None
    if loaded_config is not None:
        _config_path, effective_config = loaded_config
        if effective_config.hooks:
            hook_event_sink = create_hook_event_sink(
                hooks=effective_config.hooks,
                root=root,
                state_dir=store.state_dir,
            )

    def command_runner(
        config: CommandAdapterConfig, agent_root: Path, state_dir: Path, prompt: str
    ) -> SessionCommandResult:
        return _run_session_command_step_from_config(
            config,
            agent_root,
            state_dir,
            prompt,
            output_progress=controller.agent_output_progress,
        )

    controller = RunController(
        root=root,
        store=store,
        config_path=args.config,
        max_steps=int(args.max_steps),
        ready_prompt=_ready_prompt,
        status_snapshot=lambda session_store, repo_root: _status(session_store, repo_root),
        command_runner=command_runner,
        event_sink=compose_event_sinks(hook_event_sink),
    )
    use_tui = should_use_tui(
        output_format=str(args.format),
        no_tui=bool(getattr(args, "no_tui", False)),
        stdout_is_tty=sys.stdout.isatty(),
    )
    try:
        if use_tui:
            if textual_available():
                app = create_run_app(controller)
                result = cast(Any, app).run()
                args._tui_rendered = True
                return cast(dict[str, object], result)
            print(TUI_FALLBACK_WARNING, file=sys.stderr)
            print(TUI_INSTALL_GUIDANCE, file=sys.stderr)
        return controller.run()
    except KeyboardInterrupt:
        return _interrupted_run_result(store)


def _run_session_command_step_from_config(
    config: CommandAdapterConfig,
    root: Path,
    state_dir: Path,
    prompt: str,
    *,
    output_progress: AgentOutputProgress | None = None,
) -> SessionCommandResult:
    return _run_session_command_step(
        config=config,
        root=root,
        state_dir=state_dir,
        prompt=prompt,
        output_progress=output_progress,
    )


def _run_session_command_step(
    *,
    config: CommandAdapterConfig,
    root: Path,
    state_dir: Path,
    prompt: str,
    output_progress: AgentOutputProgress | None = None,
) -> SessionCommandResult:
    variables = {
        "repo_root": str(root.resolve()),
        "state_dir": str(state_dir.resolve()),
        "prompt": prompt,
    }
    try:
        argv = [_expand_session_template(config.command, variables)]
        argv.extend(_expand_session_template(arg, variables) for arg in config.args)
        cwd_path = _resolve_session_cwd(config, root, variables)
        env = os.environ.copy()
        env.update(
            {key: _expand_session_template(value, variables) for key, value in config.env.items()}
        )
    except ValueError as exc:
        return SessionCommandResult(
            argv=[],
            cwd=None,
            returncode=None,
            stdout="",
            stderr="",
            failure={"reason": "template_error", "error": str(exc)},
        )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    output_lock = threading.Lock()

    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd_path,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        return SessionCommandResult(
            argv=argv,
            cwd=str(cwd_path),
            returncode=None,
            stdout="",
            stderr="",
            failure={
                "reason": "startup_error",
                "error": f"command not found: {argv[0]}",
                "detail": str(exc),
            },
        )

    def read_stream(stream_name: str, lines: list[str], pipe: Any) -> None:
        try:
            for line in pipe:
                with output_lock:
                    lines.append(line)
                if output_progress is not None:
                    output_progress.push(stream_name, line.rstrip("\n"))
        finally:
            pipe.close()

    if process.stdout is None or process.stderr is None:
        raise RuntimeError("subprocess pipes were not created")
    stdout_thread = threading.Thread(
        target=read_stream,
        args=("stdout", stdout_lines, process.stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=read_stream,
        args=("stderr", stderr_lines, process.stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    try:
        returncode = process.wait(timeout=config.timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait()
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        with output_lock:
            stdout = _process_session_output_text("".join(stdout_lines))
            stderr = _process_session_output_text("".join(stderr_lines))
        return _persist_session_command_artifacts(
            state_dir,
            SessionCommandResult(
                argv=argv,
                cwd=str(cwd_path),
                returncode=None,
                stdout=stdout,
                stderr=stderr,
                failure={
                    "reason": "timeout",
                    "error": f"command timed out after {config.timeout_seconds} seconds",
                    "timeout_seconds": config.timeout_seconds,
                    "returncode_after_kill": returncode,
                },
            ),
        )
    except KeyboardInterrupt:
        process.kill()
        process.wait()
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        with output_lock:
            captured_stdout = "".join(stdout_lines)
            captured_stderr = "".join(stderr_lines)
        return SessionCommandResult(
            argv=argv,
            cwd=str(cwd_path),
            returncode=None,
            stdout=captured_stdout,
            stderr=captured_stderr,
            failure={
                "reason": RUN_INTERRUPTED_REASON,
                "error": RUN_INTERRUPTED_ERROR,
            },
        )
    stdout_thread.join()
    stderr_thread.join()
    with output_lock:
        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)
    failure: dict[str, object] | None = None
    if returncode != 0:
        failure = {
            "reason": "command_failed",
            "error": f"command exited with status {returncode}",
            "returncode": returncode,
        }
    result = SessionCommandResult(
        argv=argv,
        cwd=str(cwd_path),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        failure=failure,
    )
    return _persist_session_command_artifacts(state_dir, result)


run_session_command_step_for_testing = _run_session_command_step


def _persist_session_command_artifacts(
    state_dir: Path, result: SessionCommandResult
) -> SessionCommandResult:
    run_dir = state_dir / "runs" / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "agent-stdout.log"
    stderr_path = run_dir / "agent-stderr.log"
    activity_path = run_dir / "activity.jsonl"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    output_tail = _agent_output_tail(result.stdout, result.stderr)
    with activity_path.open("w", encoding="utf-8") as handle:
        for entry in output_tail:
            handle.write(json.dumps({"stream": entry.stream, "text": entry.text}) + "\n")
        handle.write(
            json.dumps(
                {
                    "event": "agent_completed",
                    "returncode": result.returncode,
                    "failed": result.failure is not None,
                }
            )
            + "\n"
        )
    return SessionCommandResult(
        argv=result.argv,
        cwd=result.cwd,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        failure=result.failure,
        stdout_artifact=str(stdout_path),
        stderr_artifact=str(stderr_path),
        activity_artifact=str(activity_path),
        output_tail=output_tail,
    )


def _agent_output_tail(
    stdout: str, stderr: str, *, limit: int = 20
) -> tuple[AgentOutputEntry, ...]:
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    stderr_lines = [line for line in stderr.splitlines() if line.strip()]
    entries: list[AgentOutputEntry] = []
    i = j = 0
    while i < len(stdout_lines) or j < len(stderr_lines):
        if i < len(stdout_lines):
            entries.append(AgentOutputEntry("stdout", stdout_lines[i]))
            i += 1
        if j < len(stderr_lines):
            entries.append(AgentOutputEntry("stderr", stderr_lines[j]))
            j += 1
    return tuple(entries[-limit:])


def _expand_session_template(value: str, variables: dict[str, str]) -> str:
    placeholder = "\x00REVIEW_GAUNTLET_LITERAL_BRACE\x00"
    protected = value.replace("{{", placeholder + "OPEN").replace("}}", placeholder + "CLOSE")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in _SESSION_TEMPLATE_VARIABLES:
            raise ValueError(
                f"template variable {{{name}}} is not available for run; supported variables: "
                + ", ".join(f"{{{item}}}" for item in sorted(_SESSION_TEMPLATE_VARIABLES))
            )
        return variables[name].replace("\x00", "")

    expanded = TEMPLATE_PATTERN.sub(replace, protected)
    return expanded.replace(placeholder + "OPEN", "{").replace(placeholder + "CLOSE", "}")


def _resolve_session_cwd(
    config: CommandAdapterConfig, root: Path, variables: dict[str, str]
) -> Path:
    root = root.resolve()
    if config.cwd is None:
        return root
    cwd = Path(_expand_session_template(config.cwd, variables))
    resolved = (root / cwd).resolve() if not cwd.is_absolute() else cwd.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"adapter.cwd must stay inside repository root: {resolved}") from exc
    if not resolved.is_dir():
        raise ValueError(f"adapter.cwd is not a directory: {resolved}")
    return resolved


def _emit_run(result: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"completed: {result['completed']}")
    print(f"reason: {result['reason']}")
    print(f"step_count: {result['step_count']}")
    if "error" in result:
        print(f"error: {result['error']}")
    for step in cast(list[dict[str, object]], result["steps"]):
        print(f"step {step['step']}: returncode={step['returncode']} argv={step['argv']}")
        stdout = str(step.get("stdout", ""))
        stderr = str(step.get("stderr", ""))
        if stdout:
            print(f"stdout: {stdout}")
        if stderr:
            print(f"stderr: {stderr}")


def _emit_ready(prompt: str | None, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps({"prompt": prompt}, indent=2, sort_keys=True))
        return
    print(prompt if prompt is not None else "no ready task")


def _cmd_mark(args: argparse.Namespace, store: SessionStore) -> None:
    store.active_session_id()
    metadata_states = {"accepted-risk", "waived"}
    if args.until and args.state not in metadata_states:
        raise ValueError("mark --until is only valid for waived or accepted-risk findings")
    if args.until:
        try:
            date.fromisoformat(str(args.until))
        except ValueError as exc:
            raise ValueError("mark --until must be an ISO date (YYYY-MM-DD)") from exc
    mapping = {
        "confirmed": FindingState.CONFIRMED,
        "false-positive": FindingState.FALSE_POSITIVE,
        "waived": FindingState.WAIVED,
        "accepted-risk": FindingState.ACCEPTED_RISK,
        "fixed": FindingState.FIXED_PENDING_VERIFICATION,
    }
    metadata = (
        {k: v for k, v in {"owner": args.owner, "until": args.until}.items() if v}
        if args.state in metadata_states
        else {}
    )
    store.mark_finding(args.finding_id, mapping[args.state], args.reason, metadata)
    _emit({"finding_id": args.finding_id, "state": mapping[args.state].value}, args.format)


def _cancel(store: SessionStore) -> dict[str, object]:
    session_id = store.cancel_active_session()
    return {"session_id": session_id, "session_state": "cancelled"}


def _status(
    store: SessionStore,
    root: Path,
    *,
    allow_non_review_dirty: bool = False,
) -> dict[str, object]:
    session_id = store.active_session_id()
    with store.connect() as conn:
        finding_counts = dict(
            conn.execute(
                "select state, count(*) as count from findings where session_id = ? group by state",
                (session_id,),
            ).fetchall()
        )
        run_count = conn.execute(
            "select count(*) as count from runs where session_id = ?", (session_id,)
        ).fetchone()["count"]
    effective_cell_counts = _effective_current_target_coverage(store, session_id, root)
    reasons = _finalize_reasons(
        effective_cell_counts, finding_counts, store, session_id, root, allow_non_review_dirty
    )
    return {
        "session_id": session_id,
        "session_state": "active",
        "coverage": effective_cell_counts,
        "finding_state_counts": finding_counts,
        "run_count": int(run_count),
        "can_finalize": not reasons,
        "finalize_blockers": reasons,
        "next_required_action": _next_action(effective_cell_counts, finding_counts, reasons),
    }


def _findings(
    store: SessionStore,
    *,
    include_all: bool,
    path_filters: tuple[str, ...] = (),
    mark_filters: tuple[str, ...] = (),
    limit: int | None = 10,
) -> dict[str, object]:
    if limit is not None and limit < 1:
        raise ValueError("findings --limit must be a positive integer")
    session_id = store.active_session_id()
    terminal = {state.value for state in _terminal_finding_states()}
    requested_states = {_FINDING_MARK_TO_STATE[mark].value for mark in mark_filters}
    normalized_path_filters = tuple(_normalize_finding_path(path) for path in path_filters)
    with store.connect() as conn:
        rows = list(
            conn.execute(
                """
                select
                  f.*,
                  coalesce(o.start_line, 0) as start_line,
                  coalesce(o.end_line, 0) as end_line,
                  coalesce(o.imprecise, 1) as imprecise
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
            )
        )
    findings = sorted(
        (
            dict(row)
            for row in rows
            if (include_all or row["state"] not in terminal)
            and (not requested_states or row["state"] in requested_states)
            and _matches_finding_path_filters(str(row["path"]), normalized_path_filters)
        ),
        key=_finding_sort_key,
    )
    total = len(findings)
    limited_findings = findings if limit is None else findings[:limit]
    return {
        "session_id": session_id,
        "total": total,
        "returned": len(limited_findings),
        "findings": limited_findings,
    }


def _finding_sort_key(finding: dict[str, object]) -> tuple[str, int, int, str]:
    return (
        str(finding.get("path", "")),
        _finding_int_field(finding, "start_line"),
        _finding_int_field(finding, "end_line"),
        str(finding.get("finding_id", "")),
    )


def _finding_int_field(finding: dict[str, object], key: str) -> int:
    value = finding.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _terminal_finding_states() -> set[FindingState]:
    return {
        FindingState.FIXED_VERIFIED,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
    }


def _matches_finding_path_filters(path: str, filters: tuple[str, ...]) -> bool:
    if not filters:
        return True
    normalized_path = _normalize_finding_path(path)
    return any(
        _matches_finding_path_filter(normalized_path, path_filter) for path_filter in filters
    )


def _matches_finding_path_filter(path: str, path_filter: str) -> bool:
    if path_filter.endswith("/"):
        return path.startswith(path_filter)
    return path == path_filter or path.startswith(f"{path_filter}/")


def _normalize_finding_path(path: str) -> str:
    if not path or not path.strip():
        raise ValueError("finding path filter must not be empty")
    path = path.strip()
    suffix = "/" if path.replace("\\", "/").endswith("/") else ""
    try:
        normalized = normalize_repository_relative_path(path)
    except UnsafeRepositoryPathError as exc:
        raise ValueError(f"invalid finding path filter: {path}") from exc
    result = posixpath.normpath(normalized) + suffix
    if result == "." or result == "./":
        raise ValueError(f"finding path filter must not be the repository root: {path}")
    return result


def _finalize(
    store: SessionStore,
    root: Path,
    *,
    allow_non_review_dirty: bool = False,
) -> dict[str, object]:
    status = _status(store, root, allow_non_review_dirty=allow_non_review_dirty)
    if not status["can_finalize"]:
        try:
            from review_gauntlet.checkpoint import assert_review_universe_clean

            assert_review_universe_clean(root)
        except DirtyReviewUniverseError as exc:
            blockers = cast(list[str], status["finalize_blockers"])
            if str(exc) not in blockers:
                status["finalize_blockers"] = [*blockers, str(exc)]
        return status
    try:
        checkpoint = write_latest_checkpoint(store, root, str(status["session_id"]), status)
    except DirtyReviewUniverseError as exc:
        status["can_finalize"] = False
        status["finalize_blockers"] = [*cast(list[str], status["finalize_blockers"]), str(exc)]
        status["next_required_action"] = "resolve_finalize_blockers"
        return status
    with store.connect() as conn:
        conn.execute(
            "update sessions set state = 'finalized' where session_id = ?",
            (status["session_id"],),
        )
    if store.active_path.exists():
        store.active_path.unlink()
    status.update(checkpoint)
    status["session_state"] = "finalized"
    status["can_finalize"] = True
    return status


def _finalize_reasons(
    cell_counts: dict[str, int],
    finding_counts: dict[str, int],
    store: SessionStore,
    session_id: str,
    root: Path,
    allow_non_review_dirty: bool = False,
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
    try:
        from review_gauntlet.checkpoint import assert_review_universe_clean

        assert_review_universe_clean(root)
    except DirtyReviewUniverseError as exc:
        reasons.append(str(exc))
    if not allow_non_review_dirty:
        wtd = classify_working_tree_dirty(root)
        if wtd.non_review_paths:
            reasons.append(
                "working tree has uncommitted non-review files: " + ", ".join(wtd.non_review_paths)
            )
    last_reviewed_digest = store.last_run_target_digest(session_id)
    if last_reviewed_digest is None:
        reasons.append("no review run has been completed")
    elif last_reviewed_digest != target_digest(root):
        reasons.append(_TARGET_DIGEST_DRIFT_REASON)
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
            if (
                event is not None
                and event["metadata"] is not None
                and _is_expired(str(event["metadata"]), today)
            ):
                expired += 1
    return expired


def _is_expired(metadata_json: str, today: date) -> bool:
    try:
        raw_metadata = json.loads(metadata_json)
        if not isinstance(raw_metadata, dict):
            return False
        metadata = cast(dict[str, Any], raw_metadata)
        until = metadata.get("until")
        if not until:
            return False
        return date.fromisoformat(str(until)) < today
    except (json.JSONDecodeError, ValueError, TypeError):
        print(
            "warning: unparseable metadata JSON in finding event, treating as not expired",
            file=sys.stderr,
        )
        return False


def _next_action(
    cell_counts: dict[str, int],
    finding_counts: dict[str, int],
    reasons: list[str],
) -> str:
    if cell_counts.get("pending", 0):
        return "run_review"
    if finding_counts.get("untriaged", 0) or finding_counts.get("reopened", 0):
        return "triage_findings"
    if finding_counts.get("confirmed", 0):
        return "fix_confirmed_findings"
    if finding_counts.get("fixed_pending_verification", 0):
        return "run_verify_fixes"
    if cell_counts.get("stale", 0):
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
