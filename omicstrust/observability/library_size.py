from __future__ import annotations

import numpy as np


def library_size(X) -> np.ndarray:
    return np.asarray(X.sum(axis=1)).ravel().astype(float)
