from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from omicstrust.dataset import OmicsDataset
from omicstrust.utils.serialization import make_json_safe
from omicstrust.utils.validation import MAX_SAFE_DENSE_ELEMENTS, is_sparse_matrix, matrix_nnz


def compute_qc_report(
    dataset: OmicsDataset,
    *,
    batch_key: str | None = None,
    donor_key: str | None = None,
    label_key: str | None = None,
) -> dict[str, Any]:
    X = dataset.X
    n_cells, n_features = map(int, X.shape)
    nnz = matrix_nnz(X)
    total_elements = max(1, n_cells * n_features)
    zero_fraction = float(1.0 - nnz / total_elements)
    nonzero_fraction = float(nnz / total_elements)
    data_values = X.data if is_sparse_matrix(X) else np.asarray(X)
    nan_count = int(np.isnan(data_values).sum()) if np.issubdtype(np.asarray(data_values).dtype, np.number) else 0
    inf_count = int(np.isinf(data_values).sum()) if np.issubdtype(np.asarray(data_values).dtype, np.number) else 0

    cell_total_counts = np.asarray(X.sum(axis=1)).ravel().astype(float)
    feature_total_counts = np.asarray(X.sum(axis=0)).ravel().astype(float)
    detected_genes = _axis_nnz(X, axis=1).astype(float)
    detected_cells = _axis_nnz(X, axis=0).astype(float)
    zero_fraction_per_gene = 1.0 - detected_cells / max(1, n_cells)
    pct_counts_mt = _pct_counts_mt(dataset, feature_total_counts, cell_total_counts)

    obs = dataset.obs.copy() if dataset.obs is not None else pd.DataFrame(index=range(n_cells))
    var = dataset.var.copy() if dataset.var is not None else pd.DataFrame(index=range(n_features))
    missing_metadata = _missing_metadata(obs, [batch_key, donor_key, label_key])
    batch_imbalance = _imbalance(obs, batch_key)
    donor_imbalance = _imbalance(obs, donor_key)
    label_imbalance = _imbalance(obs, label_key)

    warnings: list[str] = []
    if nan_count or inf_count:
        warnings.append("Matrix contains NaN or Inf values.")
    if zero_fraction > 0.95:
        warnings.append("Matrix is extremely sparse; signal and stability estimates may be underpowered.")
    for key, missing in missing_metadata.items():
        if missing > 0:
            warnings.append(f"Metadata key {key!r} has {missing} missing values.")
    if batch_key and batch_key not in obs.columns:
        warnings.append(f"Batch key {batch_key!r} is not available.")
    if donor_key and donor_key not in obs.columns:
        warnings.append(f"Donor key {donor_key!r} is not available.")
    if label_key and label_key not in obs.columns:
        warnings.append(f"Label key {label_key!r} is not available.")

    qc_status = "pass"
    if warnings:
        qc_status = "warning"
    if nan_count or inf_count or n_cells < 10 or n_features < 10:
        qc_status = "fail"

    metadata_confounding = {}
    if batch_key and label_key and batch_key in obs.columns and label_key in obs.columns:
        metadata_confounding["label_batch_cramers_v"] = cramers_v(obs[label_key], obs[batch_key])
    if donor_key and label_key and donor_key in obs.columns and label_key in obs.columns:
        metadata_confounding["label_donor_cramers_v"] = cramers_v(obs[label_key], obs[donor_key])

    report = {
        "n_cells": n_cells,
        "n_features": n_features,
        "matrix_shape": [n_cells, n_features],
        "sparse": is_sparse_matrix(X),
        "zero_fraction": zero_fraction,
        "nonzero_fraction": nonzero_fraction,
        "missing_values": nan_count,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "duplicated_cell_ids": int(obs.index.duplicated().sum()),
        "duplicated_gene_ids": int(var.index.duplicated().sum()),
        "identifier_warnings": _identifier_warnings(obs, var),
        "cell_metrics": {
            "total_counts_summary": summarize_vector(cell_total_counts),
            "detected_genes_summary": summarize_vector(detected_genes),
            "library_size_outliers": _iqr_outlier_count(cell_total_counts),
            "detected_gene_outliers": _iqr_outlier_count(detected_genes),
            "pct_counts_mt_summary": summarize_vector(pct_counts_mt) if pct_counts_mt is not None else None,
        },
        "feature_metrics": {
            "total_counts_summary": summarize_vector(feature_total_counts),
            "detected_cells_summary": summarize_vector(detected_cells),
            "zero_fraction_summary": summarize_vector(zero_fraction_per_gene),
            "highly_sparse_genes": int((zero_fraction_per_gene > 0.95).sum()),
        },
        "missing_metadata": missing_metadata,
        "batch_imbalance": batch_imbalance,
        "donor_imbalance": donor_imbalance,
        "label_imbalance": label_imbalance,
        "metadata_confounding": metadata_confounding,
        "qc_status": qc_status,
        "warnings": warnings,
    }
    return make_json_safe(report)


def qc_augmented_obs(dataset: OmicsDataset) -> pd.DataFrame:
    X = dataset.X
    obs = dataset.obs.copy() if dataset.obs is not None else pd.DataFrame(index=range(X.shape[0]))
    obs["total_counts"] = np.asarray(X.sum(axis=1)).ravel().astype(float)
    obs["n_genes_by_counts"] = _axis_nnz(X, axis=1).astype(float)
    pct_mt = _pct_counts_mt(dataset, np.asarray(X.sum(axis=0)).ravel().astype(float), obs["total_counts"].to_numpy())
    if pct_mt is not None:
        obs["pct_counts_mt"] = pct_mt
    return obs


def summarize_vector(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"min": 0.0, "median": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "min": float(np.min(finite)),
        "median": float(np.median(finite)),
        "mean": float(np.mean(finite)),
        "max": float(np.max(finite)),
    }


def cramers_v(left: pd.Series, right: pd.Series) -> float:
    left_clean = left.astype("object").where(left.notna(), "__missing__")
    right_clean = right.astype("object").where(right.notna(), "__missing__")
    table = pd.crosstab(left_clean, right_clean)
    if table.empty or min(table.shape) <= 1:
        return 0.0
    observed = table.to_numpy(dtype=float)
    total = observed.sum()
    row = observed.sum(axis=1, keepdims=True)
    col = observed.sum(axis=0, keepdims=True)
    expected = row @ col / max(total, 1.0)
    mask = expected > 0
    chi2 = ((observed[mask] - expected[mask]) ** 2 / expected[mask]).sum()
    phi2 = chi2 / max(total, 1.0)
    denom = min(table.shape[0] - 1, table.shape[1] - 1)
    return float(np.sqrt(phi2 / max(denom, 1)))


def _axis_nnz(X: Any, axis: int) -> np.ndarray:
    if is_sparse_matrix(X):
        return np.asarray(X.getnnz(axis=axis)).ravel().astype(int)
    return np.count_nonzero(np.asarray(X), axis=axis).astype(int)


def _pct_counts_mt(dataset: OmicsDataset, feature_totals: np.ndarray, cell_totals: np.ndarray) -> np.ndarray | None:
    if dataset.var is None:
        return None
    names = dataset.var.index.astype(str)
    if "gene_symbols" in dataset.var.columns:
        names = dataset.var["gene_symbols"].astype(str)
    mt_mask = np.asarray([name.upper().startswith("MT-") for name in names])
    if not mt_mask.any():
        return None
    X = dataset.X[:, mt_mask]
    mt_counts = np.asarray(X.sum(axis=1)).ravel().astype(float)
    denom = np.maximum(cell_totals, 1e-12)
    return 100.0 * mt_counts / denom


def _missing_metadata(obs: pd.DataFrame, keys: list[str | None]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key in keys:
        if not key:
            continue
        result[key] = int(obs[key].isna().sum()) if key in obs.columns else int(len(obs))
    return result


def _imbalance(obs: pd.DataFrame, key: str | None) -> str | None:
    if not key or key not in obs.columns or len(obs) == 0:
        return None
    values = obs[key].astype("object").where(obs[key].notna(), "__missing__")
    counts = values.value_counts(normalize=True)
    if counts.empty:
        return None
    top = float(counts.iloc[0])
    if top >= 0.85:
        return "high"
    if top >= 0.65:
        return "moderate"
    return "low"


def _iqr_outlier_count(values: np.ndarray) -> int:
    values = np.asarray(values, dtype=float)
    q1, q3 = np.quantile(values, [0.25, 0.75])
    iqr = q3 - q1
    if iqr <= 0:
        return 0
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    return int(((values < low) | (values > high)).sum())


def _identifier_warnings(obs: pd.DataFrame, var: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if int(obs.index.duplicated().sum()) > 0:
        warnings.append("duplicate_obs_names_warning")
    if int(var.index.duplicated().sum()) > 0:
        warnings.append("duplicate_var_names_warning")
    return warnings


def large_matrix_warnings(shape, preprocessing_config: dict[str, Any]) -> list[str]:
    n_cells, n_features = map(int, shape)
    n_elements = n_cells * n_features
    if n_elements <= MAX_SAFE_DENSE_ELEMENTS:
        return []
    warnings = ["large_matrix_detected"]
    if preprocessing_config.get("scale", False):
        warnings.append("large_matrix_scale_may_require_dense_memory")
    if preprocessing_config.get("hvg_selection", False):
        warnings.append("large_matrix_hvg_requires_sparse_or_chunked_variance")
    return warnings
