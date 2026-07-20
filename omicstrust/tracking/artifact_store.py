from __future__ import annotations

from pathlib import Path


def ensure_artifact_dir(run_dir: str | Path) -> Path:
    path = Path(run_dir) / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path
