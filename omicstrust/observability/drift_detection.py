from __future__ import annotations

import numpy as np


def mean_shift_score(reference: np.ndarray, observed: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=float)
    observed = np.asarray(observed, dtype=float)
    denom = float(np.std(reference) + 1e-12)
    return float(abs(np.mean(observed) - np.mean(reference)) / denom)
