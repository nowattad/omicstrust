from __future__ import annotations

import pandas as pd

from omicstrust.observability.qc_metrics import cramers_v


def label_leakage_risk(obs: pd.DataFrame, label_key: str, covariate_key: str, threshold: float = 0.8) -> dict:
    if label_key not in obs.columns or covariate_key not in obs.columns:
        return {"risk": "unknown", "score": 0.0}
    score = cramers_v(obs[label_key], obs[covariate_key])
    return {"risk": "high" if score >= threshold else "low", "score": score}
