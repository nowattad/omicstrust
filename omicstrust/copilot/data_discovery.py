from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from omicstrust.cli.inspect import inspect_dataset_cli


COLUMN_CANDIDATES = {
    "treatment": ["treatment", "therapy", "drug", "arm", "vasopressor", "intervention"],
    "outcome": ["outcome", "response", "responder", "mortality", "survival", "death"],
    "batch": ["batch", "sequencing_run", "seq_run", "center", "platform", "tech", "site"],
    "donor": ["donor", "patient_id", "subject_id", "patient", "subject", "participant"],
    "sample_id": ["sample_id", "sample", "specimen", "library_id"],
    "label": ["label", "condition", "disease", "cell_type", "celltype", "phenotype", "group", "status"],
}


def inspect_copilot_data(data_path: str | Path | None, metadata_path: str | Path | None = None) -> dict[str, Any]:
    if not data_path:
        return {"available": False, "reason": "no_data_path"}
    data_path = Path(data_path).expanduser()
    inspection = inspect_dataset_cli(data_path)
    columns = _inspection_columns(inspection)
    metadata_columns: list[str] = []
    if metadata_path:
        metadata_columns = _metadata_columns(Path(metadata_path).expanduser())
    all_columns = _dedupe(columns + metadata_columns)
    detected = detect_metadata_columns(all_columns)
    return {
        "available": True,
        "inspection": inspection,
        "metadata_columns": metadata_columns,
        "candidate_columns": detected,
        "confidence": _mapping_confidence(detected),
    }


def detect_metadata_columns(columns: list[str]) -> dict[str, str | None]:
    lower = {col.lower(): col for col in columns}
    detected = {}
    for role, candidates in COLUMN_CANDIDATES.items():
        detected[role] = _first_match(lower, candidates)
    return detected


def merge_selected_keys(explicit: dict[str, str | None], detected: dict[str, str | None], workflow: str) -> dict[str, str | None]:
    label = explicit.get("label_key")
    if not label:
        if workflow == "treatment_response_audit":
            label = detected.get("outcome") or detected.get("treatment") or detected.get("label")
        else:
            label = detected.get("label") or detected.get("outcome")
    return {
        "batch_key": explicit.get("batch_key") or detected.get("batch"),
        "donor_key": explicit.get("donor_key") or detected.get("donor"),
        "label_key": label,
        "treatment_key": explicit.get("treatment_key") or detected.get("treatment"),
        "outcome_key": explicit.get("outcome_key") or detected.get("outcome"),
        "sample_id_key": explicit.get("sample_id_key") or explicit.get("patient_id_key") or detected.get("sample_id"),
    }


def critical_missing_for_workflow(workflow: str, selected: dict[str, str | None]) -> list[str]:
    if workflow == "treatment_response_audit":
        missing = []
        if not selected.get("treatment_key"):
            missing.append("treatment label")
        if not selected.get("outcome_key"):
            missing.append("outcome column")
        return missing
    return []


def _inspection_columns(inspection: dict[str, Any]) -> list[str]:
    if inspection.get("obs_columns"):
        return [str(col) for col in inspection["obs_columns"]]
    if inspection.get("preview_columns"):
        return [str(col) for col in inspection["preview_columns"]]
    return []


def _metadata_columns(path: Path) -> list[str]:
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    frame = pd.read_csv(path, sep=sep, nrows=5)
    return [str(col) for col in frame.columns]


def _first_match(lower_columns: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in lower_columns:
            return lower_columns[candidate]
    for lowered, original in lower_columns.items():
        if any(candidate in lowered for candidate in candidates):
            return original
    return None


def _mapping_confidence(detected: dict[str, str | None]) -> str:
    hits = sum(1 for value in detected.values() if value)
    if hits >= 3:
        return "high"
    if hits >= 1:
        return "medium"
    return "low"


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
