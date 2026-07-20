from __future__ import annotations

from typing import Any

import numpy as np
from scipy import sparse

from omicstrust.utils.validation import ensure_2d_matrix


def _sparse_column_variance(X: sparse.spmatrix) -> np.ndarray:
    """Compute population variance per column without densifying."""

    X = X.tocsr()
    mean = np.asarray(X.mean(axis=0)).ravel().astype(np.float64)
    mean_sq = np.asarray(X.power(2).mean(axis=0)).ravel().astype(np.float64)
    var = mean_sq - mean**2
    return np.maximum(np.nan_to_num(var, nan=0.0, posinf=0.0, neginf=0.0), 0.0)


def _dense_column_variance_chunked(
    X: Any,
    *,
    chunk_size: int = 1024,
) -> np.ndarray:
    """Compute population variance per column in row chunks."""

    n_obs, n_features = X.shape
    sums = np.zeros(n_features, dtype=np.float64)
    sums_sq = np.zeros(n_features, dtype=np.float64)
    n_seen = 0

    for start in range(0, n_obs, chunk_size):
        end = min(start + chunk_size, n_obs)
        block = np.asarray(X[start:end], dtype=np.float64)
        if block.ndim != 2:
            raise ValueError("Expected a 2D matrix block during HVG selection.")
        sums += block.sum(axis=0)
        sums_sq += np.square(block).sum(axis=0)
        n_seen += block.shape[0]

    if n_seen == 0:
        return np.zeros(n_features, dtype=np.float64)

    mean = sums / n_seen
    var = (sums_sq / n_seen) - mean**2
    return np.maximum(np.nan_to_num(var, nan=0.0, posinf=0.0, neginf=0.0), 0.0)


def column_variance(
    X: Any,
    *,
    chunk_size: int = 1024,
) -> np.ndarray:
    """Compute feature-wise population variance safely."""

    ensure_2d_matrix(X)
    if sparse.issparse(X):
        return _sparse_column_variance(X)
    return _dense_column_variance_chunked(X, chunk_size=chunk_size)


def highly_variable_gene_mask(
    X: Any,
    n_top_genes: int = 2000,
    *,
    chunk_size: int = 1024,
) -> np.ndarray:
    """Select top genes by variance without unsafe dense conversion."""

    ensure_2d_matrix(X)
    if n_top_genes <= 0:
        raise ValueError("n_top_genes must be positive.")

    n_features = int(X.shape[1])
    n_select = min(int(n_top_genes), n_features)
    variances = column_variance(X, chunk_size=chunk_size)
    if variances.shape[0] != n_features:
        raise ValueError(
            f"Variance vector has wrong length: expected {n_features}, got {variances.shape[0]}."
        )

    # Stable deterministic tie-breaking:
    # primary = descending variance, secondary = ascending feature index.
    order = np.lexsort((np.arange(n_features), -variances))
    mask = np.zeros(n_features, dtype=bool)
    mask[order[:n_select]] = True
    return mask


def select_highly_variable_genes(
    X: Any,
    n_top_genes: int = 2000,
    *,
    chunk_size: int = 1024,
):
    """Return X restricted to selected HVGs and the boolean feature mask."""

    ensure_2d_matrix(X)
    mask = highly_variable_gene_mask(
        X,
        n_top_genes=n_top_genes,
        chunk_size=chunk_size,
    )
    if sparse.issparse(X):
        return X.tocsr()[:, mask], mask
    return X[:, mask], mask
