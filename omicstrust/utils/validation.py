from __future__ import annotations

from typing import Any

import numpy as np

MAX_SAFE_DENSE_ELEMENTS = 25_000_000


def scipy_sparse_module() -> Any | None:
    try:
        from scipy import sparse

        return sparse
    except Exception:
        return None


def is_sparse_matrix(X: Any) -> bool:
    sparse = scipy_sparse_module()
    return bool(sparse is not None and sparse.issparse(X))


def matrix_nnz(X: Any) -> int:
    if is_sparse_matrix(X):
        return int(X.nnz)
    return int(np.count_nonzero(np.asarray(X)))


def ensure_2d_matrix(X: Any, name: str = "X") -> None:
    if not hasattr(X, "shape") or len(X.shape) != 2:
        raise ValueError(f"{name} must be a two-dimensional cells x features matrix.")


def can_densify(X: Any, max_elements: int = MAX_SAFE_DENSE_ELEMENTS) -> bool:
    ensure_2d_matrix(X)
    return int(X.shape[0]) * int(X.shape[1]) <= max_elements


def to_dense_safe(X: Any, *, reason: str, max_elements: int = MAX_SAFE_DENSE_ELEMENTS) -> np.ndarray:
    ensure_2d_matrix(X)
    if not can_densify(X, max_elements=max_elements):
        raise MemoryError(
            "Matrix is too large for dense conversion during "
            f"{reason}. Use a randomized/sparse method or reduce features."
        )
    if is_sparse_matrix(X):
        return np.asarray(X.toarray(), dtype=float)
    return np.asarray(X, dtype=float)


def finite_or_raise(values: np.ndarray, name: str) -> None:
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} contains NaN or Inf values.")
