from __future__ import annotations

import numpy as np

from omicstrust.utils.validation import is_sparse_matrix


def normalize_total(X, target_sum: float = 10_000.0):
    totals = np.asarray(X.sum(axis=1)).ravel().astype(float)
    factors = np.divide(target_sum, totals, out=np.zeros_like(totals), where=totals > 0)
    if is_sparse_matrix(X):
        return X.multiply(factors[:, None]).tocsr()
    return np.asarray(X, dtype=float) * factors[:, None]
