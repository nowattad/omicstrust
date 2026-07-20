from __future__ import annotations

import numpy as np


def sort_eigenpairs(eigenvalues: np.ndarray, eigenvectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(eigenvalues)[::-1]
    return np.asarray(eigenvalues)[order], np.asarray(eigenvectors)[:, order]


def fix_eigenvector_signs(components: np.ndarray) -> np.ndarray:
    fixed = np.array(components, dtype=float, copy=True)
    for i in range(fixed.shape[0]):
        row = fixed[i]
        if row.size == 0:
            continue
        idx = int(np.argmax(np.abs(row)))
        if row[idx] < 0:
            fixed[i] *= -1
    return fixed


def eigendecompose_covariance(C: np.ndarray, n_components: int) -> tuple[np.ndarray, np.ndarray]:
    eigenvalues, eigenvectors = np.linalg.eigh(np.asarray(C, dtype=float))
    eigenvalues, eigenvectors = sort_eigenpairs(eigenvalues, eigenvectors)
    k = min(int(n_components), eigenvectors.shape[1])
    components = fix_eigenvector_signs(eigenvectors[:, :k].T)
    return eigenvalues[:k], components


def spectral_gap(eigenvalues: np.ndarray) -> np.ndarray:
    values = np.asarray(eigenvalues, dtype=float)
    if values.size <= 1:
        return np.array([], dtype=float)
    return values[:-1] - values[1:]
