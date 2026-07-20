from __future__ import annotations

import numpy as np


def select_rank_from_spectrum(eigenvalues: np.ndarray, min_rank: int = 1) -> int:
    values = np.asarray(eigenvalues, dtype=float)
    if values.size == 0:
        return 0
    positive = values[values > 0]
    if positive.size == 0:
        return min_rank
    threshold = float(np.median(positive))
    rank = int(np.sum(values > threshold))
    return max(min_rank, min(rank, values.size))
