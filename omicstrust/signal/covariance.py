from __future__ import annotations

import numpy as np

from omicstrust.utils.validation import finite_or_raise, is_sparse_matrix, to_dense_safe


def weighted_mean(X, weights=None) -> np.ndarray:
    n_cells = int(X.shape[0])
    if weights is None:
        if is_sparse_matrix(X):
            return np.asarray(X.mean(axis=0)).ravel().astype(float)
        return np.asarray(X, dtype=float).mean(axis=0)
    w = _normalized_weights(weights, n_cells)
    if is_sparse_matrix(X):
        return np.asarray(X.T @ w).ravel().astype(float)
    return np.asarray(X, dtype=float).T @ w


def weighted_covariance(
    X,
    weights=None,
    center: bool = True,
    regularization: float = 1e-8,
    normalization: str = "population",
) -> np.ndarray:
    n_cells = int(X.shape[0])
    dense = to_dense_safe(X, reason="weighted covariance")
    if weights is None:
        w = np.full(n_cells, 1.0 / max(n_cells, 1), dtype=float)
    else:
        w = _normalized_weights(weights, n_cells)
    if center:
        mean = dense.T @ w
        dense = dense - mean
    weighted = dense * np.sqrt(w[:, None])
    cov = weighted.T @ weighted
    if normalization == "sample":
        correction = 1.0 - float(np.sum(w**2))
        if correction > 0:
            cov = cov / correction
    elif normalization != "population":
        raise ValueError("normalization must be 'population' or 'sample'.")
    if regularization:
        cov = cov + float(regularization) * np.eye(cov.shape[0])
    cov = (cov + cov.T) / 2.0
    finite_or_raise(cov, "weighted covariance")
    return cov


def _normalized_weights(weights, n_cells: int) -> np.ndarray:
    w = np.asarray(weights, dtype=float).ravel()
    if w.shape[0] != n_cells:
        raise ValueError("weights length must match the number of cells.")
    if np.any(w < 0):
        raise ValueError("weights must be non-negative.")
    total = float(w.sum())
    if total <= 0:
        raise ValueError("weights must sum to a positive value.")
    return w / total
