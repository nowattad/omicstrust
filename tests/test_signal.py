from __future__ import annotations

import numpy as np

import omicstrust.signal.randomized_svd as randomized_svd
from omicstrust.signal.ssi_engine import SSIEngine


def test_ssi_shapes_sorted_and_deterministic():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(30, 8))
    a = SSIEngine(n_components=4, random_state=1).fit(X)
    b = SSIEngine(n_components=4, random_state=1).fit(X)
    assert a.components().shape == (4, 8)
    assert a.scores_.shape == (30, 4)
    assert np.all(np.diff(a.spectrum()) <= 1e-10)
    assert np.allclose(a.components(), b.components())
    assert np.isfinite(a.spectrum()).all()


def test_randomized_solver_does_not_depend_on_dense_safety_gate():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(40, 25))

    assert not hasattr(randomized_svd, "to_dense_safe")

    model = SSIEngine(n_components=5, solver="randomized", random_state=3).fit(X)

    assert model.scores_.shape == (40, 5)
    assert model.components().shape == (5, 25)
    assert model.diagnostics()["solver_used"] == "randomized_svd"
