from __future__ import annotations

import os

import pytest

from lumonox.core.config import build_monitor_config
from lumonox.core.dotenv import _parse_dotenv, load_lumonox_dotenv


def test_parse_dotenv_keeps_only_lumonox_keys_and_handles_quotes_comments_export() -> None:
    parsed = _parse_dotenv(
        "\n".join(
            [
                "# a comment",
                "",
                "LUMONOX_API_KEY=ap_plain",
                'LUMONOX_INGEST_URL="https://example.test/ingest"',
                "export LUMONOX_DEBUG='1'",
                "OTHER_SECRET=should-be-ignored",
                "malformed-line-without-equals",
            ]
        )
    )
    assert parsed == {
        "LUMONOX_API_KEY": "ap_plain",
        "LUMONOX_INGEST_URL": "https://example.test/ingest",
        "LUMONOX_DEBUG": "1",
    }


def test_load_lumonox_dotenv_loads_from_cwd(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text(
        "LUMONOX_API_KEY=ap_from_dotenv\nLUMONOX_INGEST_URL=https://x/ingest\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LUMONOX_API_KEY", raising=False)
    monkeypatch.delenv("LUMONOX_INGEST_URL", raising=False)
    assert load_lumonox_dotenv() == 2
    assert os.environ["LUMONOX_API_KEY"] == "ap_from_dotenv"


def test_load_lumonox_dotenv_never_overrides_real_env(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("LUMONOX_API_KEY=ap_from_dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUMONOX_API_KEY", "ap_from_shell")
    assert load_lumonox_dotenv() == 0
    assert os.environ["LUMONOX_API_KEY"] == "ap_from_shell"


def test_load_lumonox_dotenv_walks_up_to_parent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("LUMONOX_API_KEY=ap_parent\n")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    monkeypatch.delenv("LUMONOX_API_KEY", raising=False)
    assert load_lumonox_dotenv() == 1
    assert os.environ["LUMONOX_API_KEY"] == "ap_parent"


def test_load_lumonox_dotenv_missing_file_is_noop(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_lumonox_dotenv() == 0


def test_load_lumonox_dotenv_explicit_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = tmp_path / "custom.env"
    custom.write_text("LUMONOX_API_KEY=ap_custom\n")
    monkeypatch.delenv("LUMONOX_API_KEY", raising=False)
    assert load_lumonox_dotenv(str(custom)) == 1
    assert os.environ["LUMONOX_API_KEY"] == "ap_custom"


def test_build_monitor_config_picks_up_dotenv(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text(
        "LUMONOX_API_KEY=ap_cfg\nLUMONOX_INGEST_URL=https://cfg/ingest\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LUMONOX_API_KEY", raising=False)
    monkeypatch.delenv("LUMONOX_INGEST_URL", raising=False)
    cfg = build_monitor_config()
    assert cfg.api_key == "ap_cfg"
    assert cfg.ingest_url == "https://cfg/ingest"


def test_build_monitor_config_load_dotenv_false_skips_discovery(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("LUMONOX_API_KEY=ap_should_not_load\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LUMONOX_API_KEY", raising=False)
    cfg = build_monitor_config(load_dotenv=False)
    assert cfg.api_key is None
