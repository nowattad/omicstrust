from __future__ import annotations

import time
from typing import Any

import numpy as np

from omicstrust.risk.batch_effect import categorical_association_r2
from omicstrust.signal.signal_score import structural_signal_score
from omicstrust.utils.memory import peak_memory_mb
from omicstrust.utils.validation import to_dense_safe


def run_pca_baseline(X, obs=None, batch_key: str | None = None, n_components: int = 20) -> dict[str, Any]:
    start = time.perf_counter()
    dense = to_dense_safe(X, reason="PCA baseline")
    centered = dense - dense.mean(axis=0)
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    k = min(n_components, vt.shape[0])
    scores = centered @ vt[:k].T
    eigenvalues = (singular_values[:k] ** 2) / max(dense.shape[0] - 1, 1)
    batch_risk = 0.0
    if obs is not None and batch_key and batch_key in obs.columns and k > 0:
        batch_risk = max(categorical_association_r2(scores[:, j], obs[batch_key]) for j in range(k))
    return {
        "method": "PCA",
        "runtime_seconds": float(time.perf_counter() - start),
        "memory_mb": peak_memory_mb(),
        "batch_risk": float(batch_risk),
        "stability": None,
        "signal_score": structural_signal_score(eigenvalues),
    }
