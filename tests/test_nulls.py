from __future__ import annotations

import numpy as np

from omicstrust.nulls.calibration import classify_null_calibration, null_calibration_diagnostics
from omicstrust.nulls.empirical_null import EmpiricalNull
from omicstrust.signal.ssi_engine import SSIEngine


def test_null_thresholds_and_pvalues():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(35, 10))
    factory = lambda: SSIEngine(n_components=4, random_state=0)
    observed = factory().fit(X).spectrum()
    low = EmpiricalNull(n_permutations=5, quantile=0.5, random_state=0).fit(X, factory)
    high = EmpiricalNull(n_permutations=5, quantile=0.9, random_state=0).fit(X, factory)
    assert low.thresholds().shape == observed.shape
    assert np.all(high.thresholds() >= low.thresholds())
    pvals = high.p_values(observed)
    assert np.all((pvals >= 0) & (pvals <= 1))


def test_batch_aware_null_without_batch_falls_back_to_global():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(20, 6))
    factory = lambda: SSIEngine(n_components=3, random_state=0)
    null = EmpiricalNull(method="within_batch_permutation", n_permutations=3, random_state=0).fit(X, factory, batch=None)
    assert null.thresholds().shape == (3,)
    assert any("without batch labels" in warning for warning in null.warnings_)


def test_null_calibration_distinguishes_resolution_limit_from_miscalibration():
    p_floor = 1.0 / 21.0
    pvals = [p_floor] * 17 + [0.14, 0.28, 1.0]

    diagnostics = null_calibration_diagnostics(20, pvals)

    assert classify_null_calibration(20, pvals) == "limited_permutation_resolution"
    assert diagnostics["status"] == "limited_permutation_resolution"
    assert diagnostics["p_value_resolution"] == p_floor
    assert diagnostics["fraction_at_resolution_floor"] == 0.85
