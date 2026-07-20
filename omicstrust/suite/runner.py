from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

from omicstrust.audit import run_audit
from omicstrust.cli.inspect import inspect_dataset_cli
from omicstrust.utils.serialization import read_json, write_json


def run_audit_suite(
    inputs: list[str | Path],
    *,
    output: str | Path,
    config_path: str | Path | None = None,
    batch_key: str | None = None,
    donor_key: str | None = None,
    label_key: str | None = None,
    infer_keys: bool = True,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    output_dir = Path(output)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for input_path in inputs:
        start = time.perf_counter()
        path = Path(input_path).expanduser()
        run_name = _safe_run_name(path)
        run_dir = runs_dir / run_name
        effective_keys = _effective_keys(path, batch_key=batch_key, donor_key=donor_key, label_key=label_key, infer_keys=infer_keys)
        try:
            run_audit(path, output=run_dir, config_path=config_path, **effective_keys)
            summary = read_json(run_dir / "summary.json")
            trust = read_json(run_dir / "trust_report.json")
            rows.append(
                {
                    "input": str(path),
                    "run_dir": str(run_dir),
                    "status": "ok",
                    "runtime_seconds": time.perf_counter() - start,
                    "data_qc": summary.get("data_qc"),
                    "structural_signal": summary.get("structural_signal"),
                    "batch_risk": summary.get("batch_risk"),
                    "stability": summary.get("stability"),
                    "trust_level": trust.get("trust_level"),
                    "trust_score": trust.get("trust_score"),
                    "safe_to_interpret": trust.get("safe_to_interpret"),
                    "error": None,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "input": str(path),
                    "run_dir": str(run_dir),
                    "status": "error",
                    "runtime_seconds": time.perf_counter() - start,
                    "data_qc": None,
                    "structural_signal": None,
                    "batch_risk": None,
                    "stability": None,
                    "trust_level": None,
                    "trust_score": None,
                    "safe_to_interpret": False,
                    "error": str(exc),
                }
            )
            if not continue_on_error:
                raise
    report = {
        "status": "complete" if all(row["status"] == "ok" for row in rows) else "complete_with_errors",
        "n_inputs": len(inputs),
        "n_ok": sum(1 for row in rows if row["status"] == "ok"),
        "n_error": sum(1 for row in rows if row["status"] == "error"),
        "rows": rows,
    }
    pd.DataFrame(rows).to_csv(output_dir / "suite_report.csv", index=False)
    write_json(output_dir / "suite_report.json", report)
    return report


def _effective_keys(
    path: Path,
    *,
    batch_key: str | None,
    donor_key: str | None,
    label_key: str | None,
    infer_keys: bool,
) -> dict[str, str | None]:
    keys = {"batch_key": batch_key, "donor_key": donor_key, "label_key": label_key}
    if not infer_keys or all(value is not None for value in keys.values()):
        return keys
    try:
        suggested = inspect_dataset_cli(path).get("suggested_keys", {})
    except Exception:
        suggested = {}
    for key in keys:
        if keys[key] is None:
            keys[key] = suggested.get(key)
    return keys


def _safe_run_name(path: Path) -> str:
    stem = path.stem or "dataset"
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)
    return safe[:80]
