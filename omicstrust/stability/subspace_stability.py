from __future__ import annotations

import numpy as np


def subspace_similarity(components_a: np.ndarray, components_b: np.ndarray) -> float:
    A = _orthonormal_rows(np.asarray(components_a, dtype=float))
    B = _orthonormal_rows(np.asarray(components_b, dtype=float))
    k = min(A.shape[0], B.shape[0])
    if k == 0:
        return 0.0
    singular_values = np.linalg.svd(A[:k] @ B[:k].T, compute_uv=False)
    return float(np.clip(np.mean(singular_values[:k]), 0.0, 1.0))


def _orthonormal_rows(M: np.ndarray) -> np.ndarray:
    if M.size == 0:
        return M
    Q, _ = np.linalg.qr(M.T, mode="reduced")
    return Q.T
