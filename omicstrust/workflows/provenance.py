from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omicstrust.ingest.fingerprint import fingerprint_input
from omicstrust.utils.serialization import write_json
from omicstrust.workflows.environment_capture import capture_environment, capture_package_versions


def write_provenance(
    output_dir: str | Path,
    *,
    input_path: str | None,
    config: dict[str, Any],
    random_state: int,
    command: list[str] | None = None,
) -> dict[str, Any]:
    out = Path(output_dir) / "provenance"
    out.mkdir(parents=True, exist_ok=True)
    env = capture_environment()
    packages = capture_package_versions()
    command_history = {
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "command": command or sys.argv,
    }
    seeds = {"random_state": int(random_state)}
    fingerprints = {}
    if input_path and Path(input_path).exists():
        fingerprints[str(input_path)] = fingerprint_input(input_path)
    write_json(out / "environment.json", env)
    write_json(out / "package_versions.json", packages)
    write_json(out / "command_history.json", command_history)
    write_json(out / "random_seeds.json", seeds)
    write_json(out / "input_fingerprints.json", fingerprints)
    return {
        "environment": env,
        "package_versions": packages,
        "command_history": command_history,
        "random_seeds": seeds,
        "input_fingerprints": fingerprints,
    }
