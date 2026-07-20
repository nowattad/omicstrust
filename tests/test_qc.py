from __future__ import annotations

import numpy as np
import pandas as pd

from omicstrust.dataset import OmicsDataset
from omicstrust.observability.qc_metrics import compute_qc_report


def test_qc_counts_and_sparsity():
    X = np.array([[1, 0, 2], [0, 0, 3]], dtype=float)
    obs = pd.DataFrame({"batch": ["a", "b"]})
    var = pd.DataFrame(index=["g1", "g2", "g3"])
    report = compute_qc_report(OmicsDataset(X, obs, var, None, {}, None, None), batch_key="batch")
    assert report["n_cells"] == 2
    assert report["n_features"] == 3
    assert report["zero_fraction"] == 0.5
    assert report["batch_imbalance"] == "low"


def test_metadata_missingness():
    X = np.ones((3, 2))
    obs = pd.DataFrame({"batch": ["a", None, "b"]})
    report = compute_qc_report(OmicsDataset(X, obs, None, None, {}, None, None), batch_key="batch", donor_key="donor")
    assert report["missing_metadata"]["batch"] == 1
    assert report["missing_metadata"]["donor"] == 3
