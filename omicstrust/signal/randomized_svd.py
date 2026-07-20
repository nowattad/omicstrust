from __future__ import annotations

import numpy as np

from omicstrust.signal.spectral import fix_eigenvector_signs
from omicstrust.utils.random import rng_from_seed


def randomized_svd_components(X, n_components: int, random_state: int = 0, n_oversamples: int = 8):
    n_cells, n_features = X.shape
    k = min(int(n_components), n_cells, n_features)
    rng = rng_from_seed(random_state)
    omega = rng.normal(size=(n_features, min(n_features, k + n_oversamples)))

    mean = np.asarray(X.mean(axis=0)).ravel().astype(float)
    ones = np.ones((n_cells, 1), dtype=float)

    # Center implicitly. This keeps sparse inputs sparse and avoids creating an
    # additional centered copy when a large dataset is already stored as dense.
    Y = np.asarray(X @ omega) - ones @ (mean @ omega)[None, :]
    Q, _ = np.linalg.qr(Y, mode="reduced")
    B = np.asarray(Q.T @ X) - (Q.T @ ones) @ mean[None, :]
    _, singular_values, vt = np.linalg.svd(B, full_matrices=False)
    components = fix_eigenvector_signs(vt[:k])
    eigenvalues = (singular_values[:k] ** 2) / max(n_cells - 1, 1)
    scores = np.asarray(X @ components.T) - ones @ (mean @ components.T)[None, :]
    return eigenvalues, components, scores
