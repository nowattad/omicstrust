from __future__ import annotations

from pathlib import Path


def list_runs(root: str | Path = "results") -> list[str]:
    return [str(p) for p in Path(root).glob("*/summary.json")]
