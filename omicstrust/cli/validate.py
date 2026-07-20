from __future__ import annotations

from pathlib import Path

from omicstrust.audit import load_config
from omicstrust.ingest import load_dataset
from omicstrust.ingest.schema_validator import validate_dataset
from omicstrust.observability.qc_metrics import compute_qc_report, large_matrix_warnings


def validate_dataset_cli(data: str | Path, batch_key=None, donor_key=None, label_key=None, config_path=None) -> dict:
    dataset = load_dataset(data)
    warnings = validate_dataset(dataset)
    qc = compute_qc_report(dataset, batch_key=batch_key, donor_key=donor_key, label_key=label_key)
    config = load_config(config_path)
    warnings = warnings + qc.get("warnings", []) + _large_matrix_warnings(dataset.X.shape, config.get("preprocessing", {}))
    qc_status = qc["qc_status"]
    if warnings and qc_status == "pass":
        qc_status = "warning"
    return {"valid": True, "warnings": warnings, "shape": qc["matrix_shape"], "qc_status": qc_status}


def _large_matrix_warnings(shape, preprocessing_config: dict) -> list[str]:
    return large_matrix_warnings(shape, preprocessing_config)
