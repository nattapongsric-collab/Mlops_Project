"""Load configs/config.yaml once for the whole project."""
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def load_config(path: str | Path = ROOT / "configs" / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
