from pathlib import Path

import pytest

from review_gauntlet.config import (
    CommandAdapterConfig,
    ConfigError,
    discover_config_path,
    load_config,
)


def test_config_discovery_precedence(tmp_path: Path) -> None:
    for name in (
        "review-gauntlet.json",
        "review-gauntlet.jsonc",
        ".review-gauntlet/config.json",
        ".review-gauntlet/config.jsonc",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"adapter":{"type":"command","command":"tool"}}', encoding="utf-8")

    assert discover_config_path(tmp_path) == tmp_path / ".review-gauntlet/config.jsonc"


def test_explicit_config_takes_precedence(tmp_path: Path) -> None:
    default = tmp_path / ".review-gauntlet" / "config.jsonc"
    default.parent.mkdir(parents=True)
    default.write_text('{"adapter":{"type":"command","command":"default"}}', encoding="utf-8")
    explicit = tmp_path / "custom.json"
    explicit.write_text('{"adapter":{"type":"command","command":"custom"}}', encoding="utf-8")

    loaded = load_config(tmp_path, explicit)

    assert loaded is not None
    path, config = loaded
    assert path == explicit
    assert config.adapter.command == "custom"


def test_missing_config_returns_none(tmp_path: Path) -> None:
    assert load_config(tmp_path) is None


def test_jsonc_comments_trailing_commas_and_string_content(tmp_path: Path) -> None:
    config = tmp_path / "review-gauntlet.jsonc"
    config.write_text(
        r"""
        {
          // line comment
          "adapter": {
            "type": "command",
            "command": "tool",
            "args": ["literal // not comment", "literal /* not comment */",],
            "env": {"NOTE": "keep // text",},
          },
        }
        """,
        encoding="utf-8",
    )

    loaded = load_config(tmp_path)

    assert loaded is not None
    assert loaded[1].adapter.args == ("literal // not comment", "literal /* not comment */")
    assert loaded[1].adapter.env == {"NOTE": "keep // text"}


@pytest.mark.parametrize(
    "payload, message",
    [
        ('{"adapter":{"type":"fake","command":"tool"}}', "type"),
        ('{"adapter":{"type":"command","command":"tool --flag"}}', "shell string"),
        ('{"adapter":{"type":"command","command":"tool","input":{"mode":"bad"}}}', "input"),
        ('{"adapter":{"type":"command","command":"tool","output":{"mode":"bad"}}}', "output"),
        ('{"adapter":{"type":"command","command":"tool","unknown":1}}', "unknown"),
        (
            '{"adapter":{"type":"command","command":"tool","timeout_seconds":0}}',
            "greater than zero",
        ),
        ('{"adapter":{"type":"command","command":"tool","args":["{unknown}"]}}', "unsupported"),
        ('{"adapter":{"type":"command","command":"tool","args":["{prompt_file}"]}}', "unsupported"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, payload: str, message: str) -> None:
    config = tmp_path / "review-gauntlet.json"
    config.write_text(payload, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_config(tmp_path)


def test_command_adapter_config_accepts_prompt_and_defaults_timeout() -> None:
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": "tool",
            "args": ["run", "{prompt}"],
            "env": {"MESSAGE": "{prompt}"},
        }
    )

    assert config.args == ("run", "{prompt}")
    assert config.env == {"MESSAGE": "{prompt}"}
    assert config.timeout_seconds == 600


@pytest.mark.parametrize("name", ["MESSAGE", "_TOKEN", "A1", "PATH_WITH_UNDERSCORES"])
def test_command_adapter_config_accepts_portable_env_names(name: str) -> None:
    config = CommandAdapterConfig.model_validate(
        {"type": "command", "command": "tool", "env": {name: "value"}}
    )

    assert config.env == {name: "value"}


@pytest.mark.parametrize(
    "name",
    ["", "BAD-NAME", "1BAD", "BAD=NAME", "BAD.NAME", "BAD NAME", "BAD\x00NAME"],
)
def test_command_adapter_config_rejects_invalid_env_names(name: str) -> None:
    with pytest.raises(ValueError, match="portable environment variable names"):
        CommandAdapterConfig.model_validate(
            {"type": "command", "command": "tool", "env": {name: "value"}}
        )


@pytest.mark.parametrize(
    "value",
    ["prefix {{ suffix", "prefix }} suffix", "{{prompt}}", "json {'comments': []}"],
)
def test_command_adapter_config_accepts_literal_braces(value: str) -> None:
    config = CommandAdapterConfig.model_validate(
        {"type": "command", "command": "tool", "args": [value]}
    )

    assert config.args == (value,)


@pytest.mark.parametrize("value", ["literal { brace", "literal } brace", "{prompt", "prompt}"])
def test_command_adapter_config_rejects_unescaped_literal_braces(value: str) -> None:
    with pytest.raises(ValueError, match="literal brace"):
        CommandAdapterConfig.model_validate({"type": "command", "command": "tool", "args": [value]})


def test_command_adapter_config_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        CommandAdapterConfig.model_validate(
            {"type": "command", "command": "tool", "timeout_seconds": 0}
        )
