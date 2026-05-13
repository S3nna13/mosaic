"""Config loader + validator."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import AigisConfig


def load_config(path: str | Path) -> AigisConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    raw = yaml.safe_load(path.read_text())
    _merge_top_level(raw)
    try:
        return AigisConfig.model_validate(raw)
    except Exception as e:
        raise ValueError(f"Invalid config in {path}: {e}") from e


def validate_config(raw: dict) -> AigisConfig:
    _merge_top_level(raw)
    return AigisConfig.model_validate(raw)


def _merge_top_level(raw: dict) -> None:
    top_model = raw.get("model")
    top_name = raw.get("name")
    top_desc = raw.get("description")
    for section in ("eval", "guard"):
        sub = raw.get(section)
        if isinstance(sub, dict):
            if top_model and "model" not in sub:
                sub["model"] = top_model
            if top_name and "name" not in sub:
                sub["name"] = top_name
            if top_desc and "description" not in sub:
                sub["description"] = top_desc


__all__ = [
    "load_config",
    "validate_config",
]
