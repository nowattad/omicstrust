from __future__ import annotations

import numpy as np


def iqr_outlier_mask(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    q1, q3 = np.quantile(values, [0.25, 0.75])
    iqr = q3 - q1
    if iqr <= 0:
        return np.zeros(values.shape, dtype=bool)
    return (values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)
