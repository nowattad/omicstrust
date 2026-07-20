from __future__ import annotations

import numpy as np

from omicstrust.signal.covariance import weighted_covariance


def test_weighted_covariance_symmetry_and_manual_formula():
    X = np.array([[1.0, 2.0], [3.0, 0.0], [5.0, 4.0]])
    weights = np.array([1.0, 2.0, 1.0])
    cov = weighted_covariance(X, weights=weights, regularization=0.0)
    w = weights / weights.sum()
    centered = X - X.T @ w
    manual = centered.T @ (centered * w[:, None])
    assert np.allclose(cov, cov.T)
    assert np.allclose(cov, manual)
    assert np.isfinite(cov).all()


def test_uniform_weights_match_population_covariance():
    X = np.arange(12, dtype=float).reshape(4, 3)
    cov = weighted_covariance(X, regularization=0.0)
    assert np.allclose(cov, np.cov(X, rowvar=False, bias=True))
