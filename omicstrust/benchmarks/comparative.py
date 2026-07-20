from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from omicstrust.audit import run_audit
from omicstrust.utils.serialization import read_json, write_json


OPTIONAL_METHODS = {
    "scanpy_workflow": "scanpy",
    "scvi_style_batch_correction": "scvi",
    "harmony_batch_correction": "harmonypy",
}


def run_real_dataset_benchmark(
    input_path: str | Path,
    *,
    output: str | Path,
    batch_key: str | None = None,
    donor_key: str | None = None,
    label_key: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    audit_dir = output / "omicstrust_audit"
    run_audit(
        input_path,
        output=audit_dir,
        batch_key=batch_key,
        donor_key=donor_key,
        label_key=label_key,
        config_path=config_path,
        command=["omicstrust", "benchmark-real", str(input_path)],
    )
    baseline_path = audit_dir / "benchmark_report.csv"
    baseline_rows = pd.read_csv(baseline_path).to_dict(orient="records") if baseline_path.exists() else []
    method_status = _method_status()
    report = {
        "benchmark_type": "real_dataset_comparative_audit",
        "input_path": str(input_path),
        "audit_dir": str(audit_dir),
        "omicstrust_summary": read_json(audit_dir / "summary.json"),
        "baseline_rows": baseline_rows,
        "optional_method_status": method_status,
        "interpretation": (
            "This benchmark checks whether OmicsTrust separates statistical structure from confounding and "
            "metadata limitations while reporting baseline method behavior. Optional Scanpy/scVI/Harmony "
            "methods are recorded as available or unavailable in the local environment."
        ),
        "ruo_disclaimer": "Research Use Only. Benchmark evidence does not establish clinical validity.",
    }
    write_json(output / "comparative_benchmark.json", report)
    pd.DataFrame(_flatten_method_rows(report)).to_csv(output / "comparative_benchmark.csv", index=False)
    return report


def _method_status() -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for method, package in OPTIONAL_METHODS.items():
        try:
            __import__(package)
        except Exception as exc:
            status[method] = {
                "available": False,
                "package": package,
                "reason": str(exc),
                "note": "Optional dependency not installed; core audit remains valid.",
            }
        else:
            status[method] = {
                "available": True,
                "package": package,
                "reason": None,
                "note": "Package available. Configure a project-specific workflow before making method superiority claims.",
            }
    return status


def _flatten_method_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in report.get("baseline_rows", []):
        rows.append({"method": row.get("method"), "available": True, "signal_score": row.get("signal_score"), "batch_risk": row.get("batch_risk"), "note": row.get("warning")})
    for method, status in report.get("optional_method_status", {}).items():
        rows.append({"method": method, "available": status.get("available"), "signal_score": None, "batch_risk": None, "note": status.get("note")})
    return rows
