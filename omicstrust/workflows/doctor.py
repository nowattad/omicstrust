from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from omicstrust.cli.inspect import inspect_dataset_cli
from omicstrust.utils.serialization import write_json


REQUIRED_PACKAGES = [
    "numpy",
    "scipy",
    "pandas",
    "anndata",
    "yaml",
    "typer",
    "rich",
    "jinja2",
    "matplotlib",
]


def run_doctor(
    *,
    project_root: str | Path = ".",
    data_paths: list[str | Path] | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    checks: list[dict[str, Any]] = []
    checks.extend(_dependency_checks())
    checks.append(_writable_check(root))
    checks.append(_writable_check(root / "results"))
    for data_path in data_paths or []:
        checks.append(_dataset_check(data_path))
    status = "pass" if all(check["status"] == "pass" for check in checks) else "warning"
    report = {
        "status": status,
        "python": sys.version,
        "project_root": str(root),
        "checks": checks,
        "n_checks": len(checks),
        "n_failed": sum(1 for check in checks if check["status"] != "pass"),
    }
    if output is not None:
        write_json(Path(output) / "doctor_report.json", report)
    return report


def _dependency_checks() -> list[dict[str, Any]]:
    checks = []
    for package in REQUIRED_PACKAGES:
        checks.append(
            {
                "name": f"dependency:{package}",
                "status": "pass" if importlib.util.find_spec(package) is not None else "fail",
                "message": "available" if importlib.util.find_spec(package) is not None else "missing",
            }
        )
    return checks


def _writable_check(path: Path) -> dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".omicstrust_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"name": f"writable:{path}", "status": "pass", "message": "writable"}
    except Exception as exc:
        return {"name": f"writable:{path}", "status": "fail", "message": str(exc)}


def _dataset_check(path: str | Path) -> dict[str, Any]:
    try:
        info = inspect_dataset_cli(path)
        return {
            "name": f"dataset:{path}",
            "status": "pass",
            "message": "readable",
            "shape": info.get("shape"),
            "suggested_keys": info.get("suggested_keys"),
        }
    except Exception as exc:
        return {"name": f"dataset:{path}", "status": "fail", "message": str(exc)}
