from __future__ import annotations

import numpy as np

from omicstrust.utils.validation import is_sparse_matrix


def missing_value_count(X) -> int:
    data = X.data if is_sparse_matrix(X) else np.asarray(X)
    return int(np.isnan(data).sum())
