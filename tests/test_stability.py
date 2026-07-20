from __future__ import annotations

import numpy as np

from omicstrust.signal.ssi_engine import SSIEngine
from omicstrust.stability.bootstrap import StabilityAnalyzer


def test_stability_range_and_deterministic():
    X = np.random.default_rng(1).normal(size=(50, 12))
    factory = lambda: SSIEngine(n_components=4, random_state=2)
    a = StabilityAnalyzer(n_bootstraps=3, random_state=3).fit(X, factory).summary()
    b = StabilityAnalyzer(n_bootstraps=3, random_state=3).fit(X, factory).summary()
    assert 0 <= a["mean_subspace_similarity"] <= 1
    assert a["mean_subspace_similarity"] == b["mean_subspace_similarity"]
