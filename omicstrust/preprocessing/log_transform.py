from __future__ import annotations

import numpy as np

from omicstrust.utils.validation import is_sparse_matrix


def log1p_transform(X):
    if is_sparse_matrix(X):
        out = X.copy()
        out.data = np.log1p(out.data)
        return out
    return np.log1p(np.asarray(X, dtype=float))
