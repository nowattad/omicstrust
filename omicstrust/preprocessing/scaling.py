from __future__ import annotations

import numpy as np

from omicstrust.utils.validation import to_dense_safe


def zscore_scale(X):
    dense = to_dense_safe(X, reason="z-score scaling")
    mean = dense.mean(axis=0)
    std = dense.std(axis=0)
    std[std == 0] = 1.0
    return (dense - mean) / std
