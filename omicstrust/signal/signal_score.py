from __future__ import annotations

import numpy as np


def explained_variance_ratio(eigenvalues: np.ndarray) -> np.ndarray:
    values = np.maximum(np.asarray(eigenvalues, dtype=float), 0.0)
    total = float(values.sum())
    if total <= 0:
        return np.zeros_like(values)
    return values / total


def structural_signal_score(eigenvalues: np.ndarray) -> float:
    ratios = explained_variance_ratio(eigenvalues)
    if ratios.size == 0:
        return 0.0
    concentration = float(ratios[0])
    spread = float(np.sum(ratios[: min(5, ratios.size)]))
    return float(np.clip(0.5 * concentration + 0.5 * spread, 0.0, 1.0))
