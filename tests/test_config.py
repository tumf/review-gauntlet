import math
from pathlib import Path

import pytest

from review_gauntlet.config import (
    CommandAdapterConfig,
    ConfigError,
    discover_config_path,
    load_config,
)

CONFIG_PAYLOAD = '{"adapter":{"type":"command","command":"tool"}}'


@pytest.fixture(autouse=True)
def isolate_global_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "isolated-xdg-config"))


def test_config_discovery_precedence(tmp_path: Path) -> None:
    for name in (
        "review-gauntlet.json",
        "review-gauntlet.jsonc",
        ".review-gauntlet/config.json",
        ".review-gauntlet/config.jsonc",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CONFIG_PAYLOAD, encoding="utf-8")

    assert discover_config_path(tmp_path) == tmp_path / ".review-gauntlet/config.jsonc"


def test_global_xdg_config_is_discovered_when_repo_config_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg_home = tmp_path / "xdg-config" / ".." / "xdg-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    global_config = xdg_home.resolve() / "review-gauntlet" / "config.jsonc"
    global_config.parent.mkdir(parents=True)
    global_config.write_text(
        '{"adapter":{"type":"command","command":"global-tool"}}', encoding="utf-8"
    )

    loaded = load_config(tmp_path)

    assert loaded is not None
    path, config = loaded
    assert path == global_config
    assert config.adapter.command == "global-tool"
    assert not (tmp_path / ".review-gauntlet").exists()


def test_repo_local_config_takes_precedence_over_global_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg_home = tmp_path / "xdg-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    global_config = xdg_home / "review-gauntlet" / "config.jsonc"
    global_config.parent.mkdir(parents=True)
    global_config.write_text(
        '{"adapter":{"type":"command","command":"global-tool"}}', encoding="utf-8"
    )
    local_config = tmp_path / ".review-gauntlet" / "config.jsonc"
    local_config.parent.mkdir(parents=True)
    local_config.write_text(
        '{"adapter":{"type":"command","command":"local-tool"}}', encoding="utf-8"
    )

    loaded = load_config(tmp_path)

    assert loaded is not None
    path, config = loaded
    assert path == local_config
    assert config.adapter.command == "local-tool"


def test_unset_xdg_config_home_falls_back_to_home_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: home)
    global_config = home / ".config" / "review-gauntlet" / "config.jsonc"
    global_config.parent.mkdir(parents=True)
    global_config.write_text(
        '{"adapter":{"type":"command","command":"home-tool"}}', encoding="utf-8"
    )

    loaded = load_config(tmp_path)

    assert loaded is not None
    path, config = loaded
    assert path == global_config
    assert config.adapter.command == "home-tool"


def test_explicit_config_rejects_out_of_repo_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-review-gauntlet.json"
    outside.write_text('{"adapter":{"type":"command","command":"tool"}}', encoding="utf-8")

    with pytest.raises(ConfigError, match="inside repository root"):
        load_config(tmp_path, outside)


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


@pytest.mark.parametrize(
    "value",
    ["literal { brace", "literal } brace", "{prompt", "prompt}", "{{repo_root}"],
)
def test_command_adapter_config_rejects_unescaped_literal_braces(value: str) -> None:
    with pytest.raises(ValueError, match="literal brace"):
        CommandAdapterConfig.model_validate({"type": "command", "command": "tool", "args": [value]})


@pytest.mark.parametrize("timeout", [0, -1, math.inf, -math.inf, math.nan])
def test_command_adapter_config_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite value greater than zero"):
        CommandAdapterConfig.model_validate(
            {"type": "command", "command": "tool", "timeout_seconds": timeout}
        )


def test_command_adapter_config_rejects_prompt_in_output_path_but_not_args_or_env() -> None:
    with pytest.raises(ValueError, match="adapter.output.path must not use .*prompt"):
        CommandAdapterConfig.model_validate(
            {
                "type": "command",
                "command": "tool",
                "args": ["{prompt}"],
                "env": {"PROMPT": "{prompt}"},
                "output": {"mode": "file-json", "path": "{prompt}.json"},
            }
        )

    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": "tool",
            "args": ["{prompt}"],
            "env": {"PROMPT": "{prompt}"},
            "output": {"mode": "file-json", "path": "{output_file}"},
        }
    )
    assert config.args == ("{prompt}",)
    assert config.env == {"PROMPT": "{prompt}"}
