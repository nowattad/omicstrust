from __future__ import annotations

import numpy as np
import pandas as pd

from omicstrust.utils.validation import to_dense_safe


def residualize_covariates(X, obs: pd.DataFrame, covariates: list[str]):
    available = [key for key in covariates if key in obs.columns]
    if not available:
        return X, {"used_covariates": [], "warning": "No requested covariates were available."}
    dense = to_dense_safe(X, reason="covariate residualization")
    design_parts = [np.ones((dense.shape[0], 1))]
    used: list[str] = []
    for key in available:
        series = obs[key]
        if pd.api.types.is_numeric_dtype(series):
            values = series.astype(float).fillna(series.astype(float).median()).to_numpy()[:, None]
            design_parts.append(values)
            used.append(key)
        else:
            encoded = pd.get_dummies(series.fillna("__missing__"), drop_first=True, dtype=float)
            if encoded.shape[1] > 0:
                design_parts.append(encoded.to_numpy(dtype=float))
                used.append(key)
    design = np.hstack(design_parts)
    beta, *_ = np.linalg.lstsq(design, dense, rcond=None)
    fitted = design @ beta
    return dense - fitted + dense.mean(axis=0), {"used_covariates": used}
