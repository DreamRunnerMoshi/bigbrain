"""Unit tests for bigbrain.common.config."""

import pytest
from pydantic import ValidationError

from bigbrain.common.config import RuntimeMode, Settings, load_config


def test_load_config_none_gives_defaults() -> None:
    settings = load_config(None)

    assert settings == Settings()
    assert settings.mode is RuntimeMode.REPLAY
    assert settings.llm_enabled is False


def test_load_config_missing_file_gives_defaults(tmp_path) -> None:
    assert load_config(tmp_path / "absent.yaml") == Settings()


def test_load_config_reads_overrides_from_yaml(tmp_path) -> None:
    path = tmp_path / "bigbrain.yaml"
    path.write_text("mode: live\nseed: 42\n", encoding="utf-8")

    settings = load_config(path)

    assert settings.mode is RuntimeMode.LIVE
    assert settings.seed == 42


def test_load_config_treats_empty_file_as_defaults(tmp_path) -> None:
    path = tmp_path / "bigbrain.yaml"
    path.write_text("", encoding="utf-8")

    assert load_config(path) == Settings()


def test_load_config_rejects_invalid_values(tmp_path) -> None:
    path = tmp_path / "bigbrain.yaml"
    path.write_text("mode: not-a-mode\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)
