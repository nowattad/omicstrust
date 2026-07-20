from __future__ import annotations

import numpy as np
import pandas as pd

from omicstrust.baselines.pca import run_pca_baseline


def test_pca_baseline_output():
    X = np.random.default_rng(0).normal(size=(30, 8))
    obs = pd.DataFrame({"batch": ["a", "b"] * 15})
    row = run_pca_baseline(X, obs=obs, batch_key="batch", n_components=3)
    assert row["method"] == "PCA"
    assert 0 <= row["signal_score"] <= 1
