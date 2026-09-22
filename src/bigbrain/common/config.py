"""Runtime configuration: strict pydantic settings, optionally loaded from a YAML file."""

import os
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class RuntimeMode(str, Enum):  # noqa: UP042 -- StrEnum reads the same; spec pins the base classes
    """The four runtime modes of spec section 3; all of them share the same code."""

    SIM = "sim"
    REPLAY = "replay"
    LIVE = "live"
    NET = "net"


class Settings(BaseModel):
    """Settings for one run; default mode is REPLAY (offline, no API keys) per
    BIGBRAIN_SPEC.md §0 item 6 -- sim/live/net are opt-in via config.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    mode: RuntimeMode = RuntimeMode.REPLAY
    llm_enabled: bool = False
    llm_model_cheap: str = "claude-haiku-4-5-20251001"
    llm_model_quality: str = "claude-sonnet-5"
    data_dir: Path = Path("data")
    fixtures_dir: Path = Path("fixtures/shopify")
    results_dir: Path = Path("results")
    audit_dir: Path = Path("audit")
    log_level: str = "INFO"
    seed: int = 0
    shopify_agent_profile_url: str | None = None


def load_config(path: str | os.PathLike | None = None) -> Settings:
    """Load settings from `path`; a missing file (or `None`) means all defaults.

    Bad values raise pydantic's ValidationError -- nothing is swallowed here. YAML is a
    text format, so the file itself is validated in lax mode (str -> RuntimeMode/Path);
    the model stays strict for programmatic construction.
    """
    if path is None or not Path(path).exists():
        return Settings()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Settings.model_validate(data, strict=False)
