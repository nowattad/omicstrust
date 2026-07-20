from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from omicstrust.risk.batch_effect import numeric_association_r2
from omicstrust.utils.serialization import make_json_safe


SPATIAL_ROW_KEYS = ("array_row", "row", "spatial_row", "pxl_row_in_fullres")
SPATIAL_COL_KEYS = ("array_col", "col", "spatial_col", "pxl_col_in_fullres")
TISSUE_KEYS = ("in_tissue", "tissue", "is_tissue")


def compute_spatial_report(obs: pd.DataFrame | None, scores: np.ndarray | None = None) -> dict[str, Any]:
    if obs is None or obs.empty:
        return _not_available("No observation metadata was available.")
    row_key = _find_key(obs, SPATIAL_ROW_KEYS)
    col_key = _find_key(obs, SPATIAL_COL_KEYS)
    tissue_key = _find_key(obs, TISSUE_KEYS)
    if row_key is None or col_key is None:
        return _not_available("Spatial coordinate columns were not detected.")

    row = pd.to_numeric(obs[row_key], errors="coerce")
    col = pd.to_numeric(obs[col_key], errors="coerce")
    valid = row.notna() & col.notna()
    duplicate_locations = int(pd.DataFrame({"row": row[valid], "col": col[valid]}).duplicated().sum())
    coordinate_summary = {
        "row_key": row_key,
        "col_key": col_key,
        "n_spots": int(len(obs)),
        "n_valid_coordinates": int(valid.sum()),
        "row_min": float(row[valid].min()) if valid.any() else None,
        "row_max": float(row[valid].max()) if valid.any() else None,
        "col_min": float(col[valid].min()) if valid.any() else None,
        "col_max": float(col[valid].max()) if valid.any() else None,
        "duplicate_locations": duplicate_locations,
    }
    coordinate_preview = (
        pd.DataFrame({"row": row[valid].astype(float), "col": col[valid].astype(float)})
        .head(5000)
        .to_dict(orient="records")
    )
    tissue_summary = None
    warnings: list[str] = []
    if tissue_key is not None:
        tissue = pd.to_numeric(obs[tissue_key], errors="coerce")
        tissue_summary = {
            "tissue_key": tissue_key,
            "tissue_fraction": float(tissue.fillna(0).astype(float).mean()),
            "missing_tissue_values": int(tissue.isna().sum()),
        }
    if duplicate_locations > 0:
        warnings.append("Duplicate spatial coordinates were detected.")
    if int(valid.sum()) < len(obs):
        warnings.append("Some observations are missing spatial coordinates.")

    component_spatial_r2 = []
    if scores is not None and valid.any():
        scores_arr = np.asarray(scores, dtype=float)
        for component_idx in range(scores_arr.shape[1]):
            component = scores_arr[:, component_idx]
            component_spatial_r2.append(
                {
                    "component": component_idx + 1,
                    "row_r2": numeric_association_r2(component, row),
                    "col_r2": numeric_association_r2(component, col),
                }
            )

    max_coordinate_r2 = 0.0
    for item in component_spatial_r2:
        max_coordinate_r2 = max(max_coordinate_r2, float(item["row_r2"]), float(item["col_r2"]))
    risk = "low"
    if max_coordinate_r2 >= 0.5:
        risk = "high"
        warnings.append("A leading component is strongly associated with spatial coordinates.")
    elif max_coordinate_r2 >= 0.25:
        risk = "moderate"

    return make_json_safe(
        {
            "available": True,
            "coordinate_summary": coordinate_summary,
            "coordinate_preview": coordinate_preview,
            "tissue_summary": tissue_summary,
            "component_spatial_r2": component_spatial_r2,
            "max_coordinate_r2": max_coordinate_r2,
            "spatial_risk": risk,
            "warnings": warnings,
        }
    )


def _find_key(obs: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    lowered = {str(column).lower(): str(column) for column in obs.columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _not_available(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "warnings": []}
