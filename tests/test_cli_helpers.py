from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from review_gauntlet.cli import (
    _agent_output_tail,  # pyright: ignore[reportPrivateUsage]
    _config_init_output_path,  # pyright: ignore[reportPrivateUsage]
    _expand_session_template,  # pyright: ignore[reportPrivateUsage]
    _finding_int_field,  # pyright: ignore[reportPrivateUsage]
    _finding_sort_key,  # pyright: ignore[reportPrivateUsage]
    _is_expired,  # pyright: ignore[reportPrivateUsage]
    _matches_finding_path_filter,  # pyright: ignore[reportPrivateUsage]
    _non_negative_int,  # pyright: ignore[reportPrivateUsage]
    _normalize_finding_path,  # pyright: ignore[reportPrivateUsage]
    _process_session_output_text,  # pyright: ignore[reportPrivateUsage]
)
from review_gauntlet.run_controller import AgentOutputEntry

# --- _finding_int_field ---


def test_finding_int_field_returns_int_value() -> None:
    assert _finding_int_field({"line": 42}, "line") == 42


def test_finding_int_field_parses_string_value() -> None:
    assert _finding_int_field({"line": "7"}, "line") == 7


def test_finding_int_field_returns_zero_for_unparseable_string() -> None:
    assert _finding_int_field({"line": "abc"}, "line") == 0


def test_finding_int_field_returns_zero_for_missing_key() -> None:
    assert _finding_int_field({}, "line") == 0


def test_finding_int_field_returns_zero_for_none_value() -> None:
    assert _finding_int_field({"line": None}, "line") == 0


# --- _finding_sort_key ---


def test_finding_sort_key_extracts_tuple() -> None:
    finding: dict[str, object] = {
        "path": "a.py",
        "start_line": 10,
        "end_line": 20,
        "finding_id": "F-1",
    }
    assert _finding_sort_key(finding) == ("a.py", 10, 20, "F-1")


def test_finding_sort_key_handles_missing_fields() -> None:
    assert _finding_sort_key({}) == ("", 0, 0, "")


# --- _matches_finding_path_filter ---


def test_matches_finding_path_filter_exact_match() -> None:
    assert _matches_finding_path_filter("src/app.py", "src/app.py") is True


def test_matches_finding_path_filter_directory_prefix() -> None:
    assert _matches_finding_path_filter("src/app.py", "src/") is True


def test_matches_finding_path_filter_non_directory_prefix() -> None:
    assert _matches_finding_path_filter("src/app.py", "src") is True


def test_matches_finding_path_filter_no_match() -> None:
    assert _matches_finding_path_filter("lib/app.py", "src/") is False


# --- _normalize_finding_path ---


def test_normalize_finding_path_normalizes_simple_relative() -> None:
    assert _normalize_finding_path("src/app.py") == "src/app.py"


def test_normalize_finding_path_rejects_parent_traversal() -> None:
    with pytest.raises(ValueError, match="invalid finding path filter"):
        _normalize_finding_path("src/../src/app.py")


def test_normalize_finding_path_preserves_trailing_slash() -> None:
    result = _normalize_finding_path("src/")
    assert result.endswith("/")


def test_normalize_finding_path_rejects_unsafe_path() -> None:
    with pytest.raises(ValueError, match="invalid finding path filter"):
        _normalize_finding_path("../../etc/passwd")


# --- _process_session_output_text ---


def test_process_session_output_text_returns_empty_for_none() -> None:
    assert _process_session_output_text(None) == ""


def test_process_session_output_text_decodes_bytes() -> None:
    assert _process_session_output_text(b"hello") == "hello"


def test_process_session_output_text_replaces_invalid_bytes() -> None:
    result = _process_session_output_text(b"hello\xff")
    assert "hello" in result
    assert "�" in result


def test_process_session_output_text_returns_string_unchanged() -> None:
    assert _process_session_output_text("hello") == "hello"


# --- _agent_output_tail ---


def test_agent_output_tail_combines_stdout_and_stderr() -> None:
    result = _agent_output_tail("line1\nline2\n", "err1\n")
    assert result == (
        AgentOutputEntry("stdout", "line1"),
        AgentOutputEntry("stderr", "err1"),
        AgentOutputEntry("stdout", "line2"),
    )


def test_agent_output_tail_skips_blank_lines() -> None:
    result = _agent_output_tail("a\n\n  \nb\n", "")
    assert result == (
        AgentOutputEntry("stdout", "a"),
        AgentOutputEntry("stdout", "b"),
    )


def test_agent_output_tail_truncates_to_limit() -> None:
    stdout = "\n".join(f"line{i}" for i in range(30)) + "\n"
    result = _agent_output_tail(stdout, "", limit=5)
    assert len(result) == 5
    assert result[0].text == "line25"
    assert result[-1].text == "line29"


def test_agent_output_tail_returns_empty_for_empty_input() -> None:
    assert _agent_output_tail("", "") == ()


# --- _expand_session_template ---


def test_expand_session_template_substitutes_variables() -> None:
    result = _expand_session_template(
        "{repo_root}/out", {"repo_root": "/tmp/repo", "state_dir": "/tmp/state", "prompt": ""}
    )
    assert result == "/tmp/repo/out"


def test_expand_session_template_preserves_literal_braces() -> None:
    result = _expand_session_template(
        "{{literal}}", {"repo_root": "", "state_dir": "", "prompt": ""}
    )
    assert result == "{literal}"


def test_expand_session_template_mixed_literal_and_variable() -> None:
    result = _expand_session_template(
        "{{keep}} {repo_root} {{also}}", {"repo_root": "ROOT", "state_dir": "", "prompt": ""}
    )
    assert result == "{keep} ROOT {also}"


def test_expand_session_template_rejects_unknown_variable() -> None:
    with pytest.raises(ValueError, match="not available for run"):
        _expand_session_template("{unknown_var}", {"repo_root": "", "state_dir": "", "prompt": ""})


# --- _is_expired ---


def test_is_expired_returns_true_when_past_until_date() -> None:
    metadata = '{"until": "2024-01-01"}'
    assert _is_expired(metadata, date(2024, 6, 1)) is True


def test_is_expired_returns_false_when_before_until_date() -> None:
    metadata = '{"until": "2025-12-31"}'
    assert _is_expired(metadata, date(2024, 6, 1)) is False


def test_is_expired_returns_false_when_no_until_key() -> None:
    assert _is_expired('{"reason": "test"}', date(2024, 6, 1)) is False


def test_is_expired_returns_false_for_non_dict_json() -> None:
    assert _is_expired("[1, 2, 3]", date(2024, 6, 1)) is False


def test_is_expired_returns_false_and_warns_for_malformed_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _is_expired("not json at all", date(2024, 6, 1))
    assert result is False
    assert "unparseable metadata JSON" in capsys.readouterr().err


def test_is_expired_returns_false_and_warns_for_bad_date_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _is_expired('{"until": "not-a-date"}', date(2024, 6, 1))
    assert result is False
    assert "unparseable metadata JSON" in capsys.readouterr().err


# --- _config_init_output_path (RGF-0395) ---


def test_config_init_output_path_expands_tilde() -> None:
    args = argparse.Namespace(output=Path("~/some/config.toml"), global_config=False)
    root = Path("/tmp/repo")
    result = _config_init_output_path(args, root)
    assert result == Path.home() / "some" / "config.toml"


# --- _normalize_finding_path empty path (RGF-0394) ---


def test_normalize_finding_path_rejects_empty_string() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _normalize_finding_path("")


def test_normalize_finding_path_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _normalize_finding_path("   ")


# --- _non_negative_int (RGF-0392) ---


def test_non_negative_int_rejects_negative() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _non_negative_int("-1")


def test_non_negative_int_accepts_zero() -> None:
    assert _non_negative_int("0") == 0


def test_non_negative_int_accepts_positive() -> None:
    assert _non_negative_int("5") == 5
