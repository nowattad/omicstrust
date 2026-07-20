from __future__ import annotations

import numpy as np
import pandas as pd

from omicstrust.risk.batch_effect import component_covariate_associations, detect_batch_dominated_components


def test_detects_planted_batch_effect():
    batch = np.array(["a"] * 20 + ["b"] * 20)
    scores = np.column_stack([np.r_[np.zeros(20), np.ones(20)], np.random.default_rng(0).normal(size=40)])
    obs = pd.DataFrame({"batch": batch})
    assoc = component_covariate_associations(scores, obs, ["batch"])
    dominated = detect_batch_dominated_components(assoc, threshold=0.5, batch_keys=["batch"])
    assert dominated.iloc[0]["risk"] == "high"


def test_missing_batch_key_graceful():
    scores = np.ones((5, 2))
    assoc = component_covariate_associations(scores, pd.DataFrame({"x": range(5)}), ["batch"])
    assert assoc["available"].eq(False).all()
