from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omicstrust.utils.serialization import write_json


class LocalRunTracker:
    def __init__(self, root: str | Path = "results/runs"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def log_run(self, *, config: dict[str, Any], metrics: dict[str, Any], artifacts: list[str], warnings: list[str], failure_modes: list[dict[str, Any]]) -> dict[str, Any]:
        run = {
            "run_id": str(uuid.uuid4()),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "config": config,
            "metrics": metrics,
            "artifacts": artifacts,
            "warnings": warnings,
            "failure_modes": failure_modes,
        }
        write_json(self.root / f"{run['run_id']}.json", run)
        return run
