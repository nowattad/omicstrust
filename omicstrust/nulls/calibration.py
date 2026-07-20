from __future__ import annotations

from typing import Any

import numpy as np


def calibration_curve(expected_fpr, observed_fpr):
    expected = np.asarray(expected_fpr, dtype=float)
    observed = np.asarray(observed_fpr, dtype=float)
    return {"expected_fpr": expected, "observed_fpr": observed}


def empirical_fdr(observed, null, threshold) -> float:
    observed = np.asarray(observed, dtype=float)
    null = np.asarray(null, dtype=float)
    observed_hits = max(int(np.sum(observed >= threshold)), 1)
    null_hits = float(np.mean(np.sum(null >= threshold, axis=1))) if null.ndim == 2 else float(np.sum(null >= threshold))
    return float(np.clip(null_hits / observed_hits, 0.0, 1.0))


def null_qq_data(observed, null):
    observed = np.sort(np.asarray(observed, dtype=float))
    null_flat = np.sort(np.asarray(null, dtype=float).ravel())
    n = min(observed.size, null_flat.size)
    if n == 0:
        return {"observed": [], "null": []}
    q = np.linspace(0, 1, n)
    return {
        "observed": np.quantile(observed, q),
        "null": np.quantile(null_flat, q),
    }


def calibration_error(expected, observed) -> float:
    expected = np.asarray(expected, dtype=float)
    observed = np.asarray(observed, dtype=float)
    if expected.size == 0 or expected.shape != observed.shape:
        return float("nan")
    return float(np.mean(np.abs(expected - observed)))


def classify_null_calibration(n_permutations: int, empirical_p_values) -> str:
    return str(null_calibration_diagnostics(n_permutations, empirical_p_values)["status"])


def null_calibration_diagnostics(n_permutations: int, empirical_p_values) -> dict[str, Any]:
    pvals = np.asarray(empirical_p_values, dtype=float)
    n_permutations = int(n_permutations)
    p_value_resolution = 1.0 / max(n_permutations + 1, 1)
    result: dict[str, Any] = {
        "status": "underpowered",
        "n_permutations": n_permutations,
        "p_value_resolution": p_value_resolution,
        "fraction_below_0_05": None,
        "fraction_at_resolution_floor": None,
        "interpretation": "No empirical p-values were available for null calibration.",
    }
    if n_permutations < 20:
        result["status"] = "insufficient_permutations"
        result["interpretation"] = (
            "The empirical null has fewer than 20 permutations, so thresholding is only a rough smoke test."
        )
        return result
    if pvals.size == 0:
        return result

    pvals = pvals[np.isfinite(pvals)]
    if pvals.size == 0:
        return result

    low = float(np.mean(pvals < 0.05))
    at_floor = float(np.mean(pvals <= p_value_resolution + 1e-12))
    result["fraction_below_0_05"] = low
    result["fraction_at_resolution_floor"] = at_floor

    if n_permutations < 100 and at_floor > 0.5:
        result["status"] = "limited_permutation_resolution"
        result["interpretation"] = (
            "Many empirical p-values are at the minimum resolvable value for the current permutation count; "
            "the signal may be real, but calibration precision is coarse."
        )
        return result
    if low > 0.5:
        result["status"] = "anti-conservative"
        result["interpretation"] = (
            "A large fraction of empirical p-values are below 0.05 even after accounting for permutation resolution."
        )
        return result
    if low < 0.02:
        result["status"] = "conservative"
        result["interpretation"] = "The empirical null is conservative at the 0.05 tail."
        return result
    result["status"] = "acceptable"
    result["interpretation"] = "The empirical null calibration is acceptable at the current resolution."
    return result
