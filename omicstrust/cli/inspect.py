from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

BATCH_KEY_CANDIDATES = [
    "batch",
    "batch_id",
    "batchid",
    "tech",
    "technology",
    "platform",
    "dataset",
    "study",
    "sample",
    "sample_id",
    "library",
    "library_id",
    "chemistry",
    "seq_batch",
    "sequencing_batch",
    "orig.ident",
    "lane",
]

DONOR_KEY_CANDIDATES = [
    "donor",
    "donor_id",
    "subject",
    "subject_id",
    "subject.subjectguid",
    "patient",
    "patient_id",
    "individual",
    "individual_id",
    "participant",
    "case",
]

LABEL_KEY_CANDIDATES = [
    "celltype",
    "cell_type",
    "celltypes",
    "cell_type_major",
    "cell_type_minor",
    "annotation",
    "label",
    "condition",
    "disease",
    "diagnosis",
    "phenotype",
    "status",
    "group",
    "aifi_l1",
    "aifi_l2",
    "aifi_l3",
]


def inspect_dataset_cli(data: str | Path) -> dict[str, Any]:
    path = Path(data).expanduser()
    if not path.exists():
        raise FileNotFoundError(_missing_file_message(path))
    suffix = path.suffix.lower()
    if suffix == ".h5ad":
        return _inspect_h5ad(path)
    if suffix in {".csv", ".tsv", ".txt"}:
        return _inspect_table(path)
    raise ValueError(f"Unsupported input format: {path.suffix}. Supported formats: .h5ad, .csv, .tsv, .txt")


def _inspect_h5ad(path: Path) -> dict[str, Any]:
    try:
        import anndata as ad
    except Exception as exc:
        raise ImportError("Inspecting .h5ad files requires the optional dependency 'anndata'.") from exc
    try:
        adata = ad.read_h5ad(path, backed="r")
    except OSError as exc:
        raise ValueError(f"Could not inspect {path} as a valid .h5ad file: {exc}") from exc
    obs_columns = [str(c) for c in adata.obs.columns]
    var_columns = [str(c) for c in adata.var.columns]
    layers = [str(k) for k in adata.layers.keys()]
    return {
        "path": str(path),
        "format": "h5ad",
        "shape": [int(adata.n_obs), int(adata.n_vars)],
        "obs_columns": obs_columns,
        "var_columns": var_columns,
        "layers": layers,
        "suggested_keys": suggest_metadata_keys(obs_columns),
        "next_step": "Use the suggested keys, or choose exact names from obs_columns, then run omicstrust validate/audit.",
    }


def _inspect_table(path: Path) -> dict[str, Any]:
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    frame = pd.read_csv(path, sep=sep, nrows=5)
    return {
        "path": str(path),
        "format": path.suffix.lower().lstrip("."),
        "preview_rows": int(frame.shape[0]),
        "preview_columns": [str(c) for c in frame.columns],
        "suggested_keys": suggest_metadata_keys([str(c) for c in frame.columns]),
    }


def suggest_metadata_keys(columns: list[str]) -> dict[str, str | None]:
    lower = {c.lower(): c for c in columns}
    return {
        "batch_key": _first_match(lower, BATCH_KEY_CANDIDATES),
        "donor_key": _first_match(lower, DONOR_KEY_CANDIDATES),
        "label_key": _first_match(lower, LABEL_KEY_CANDIDATES),
    }


def _first_match(lower_columns: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in lower_columns:
            return lower_columns[candidate]
    for lowered, original in lower_columns.items():
        if any(candidate in lowered for candidate in candidates):
            return original
    return None


def _missing_file_message(path: Path) -> str:
    return (
        f"Input file not found: {path}\n"
        "Replace the example path with a real .h5ad path. You can find files with:\n"
        "  find ~/Desktop ~/Downloads ~/Documents -name \"*.h5ad\" 2>/dev/null"
    )
