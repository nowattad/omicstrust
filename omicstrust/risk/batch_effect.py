from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def categorical_association_r2(scores, categories) -> float:
    y = np.asarray(scores, dtype=float).ravel()
    raw = pd.Series(categories)
    cat = raw.astype("object").where(raw.notna(), "__missing__")
    if y.size != len(cat) or y.size < 3 or cat.nunique() <= 1:
        return 0.0
    design = pd.get_dummies(cat, drop_first=False, dtype=float).to_numpy()
    return _linear_r2(y, design)


def numeric_association_r2(scores, covariate) -> float:
    y = np.asarray(scores, dtype=float).ravel()
    x = pd.Series(covariate).astype(float)
    if y.size != len(x) or y.size < 3:
        return 0.0
    x = x.fillna(float(x.median())).to_numpy()[:, None]
    if float(np.nanstd(x)) <= 1e-12:
        return 0.0
    return _linear_r2(y, x)


def component_covariate_associations(scores, obs: pd.DataFrame, keys: Iterable[str]) -> pd.DataFrame:
    scores_arr = np.asarray(scores, dtype=float)
    rows: list[dict[str, object]] = []
    for component_idx in range(scores_arr.shape[1]):
        component = scores_arr[:, component_idx]
        for key in keys:
            if not key or key not in obs.columns:
                rows.append(
                    {
                        "component": component_idx + 1,
                        "covariate": key,
                        "covariate_type": "missing",
                        "r2": 0.0,
                        "available": False,
                    }
                )
                continue
            series = obs[key]
            if pd.api.types.is_numeric_dtype(series):
                r2 = numeric_association_r2(component, series)
                ctype = "numeric"
            else:
                r2 = categorical_association_r2(component, series)
                ctype = "categorical"
            rows.append(
                {
                    "component": component_idx + 1,
                    "covariate": key,
                    "covariate_type": ctype,
                    "r2": float(r2),
                    "available": True,
                }
            )
    return pd.DataFrame(rows)


def detect_batch_dominated_components(
    associations: pd.DataFrame,
    threshold: float = 0.5,
    *,
    batch_keys: Iterable[str] = ("batch", "donor"),
    label_key: str | None = None,
) -> pd.DataFrame:
    if associations.empty:
        return pd.DataFrame(columns=["component", "risk", "decision", "max_batch_r2", "label_r2"])
    batch_set = set(k for k in batch_keys if k)
    rows: list[dict[str, object]] = []
    for component, frame in associations.groupby("component"):
        batch_values = pd.to_numeric(frame.loc[frame["covariate"].isin(batch_set), "r2"], errors="coerce").dropna()
        batch_r2 = float(batch_values.max()) if not batch_values.empty else 0.0
        label_r2 = 0.0
        if label_key:
            label_values = pd.to_numeric(frame.loc[frame["covariate"] == label_key, "r2"], errors="coerce").dropna()
            label_r2 = float(label_values.max()) if not label_values.empty else 0.0
        risk = "low"
        decision = "safe_to_audit_further"
        if batch_r2 >= threshold and batch_r2 >= label_r2:
            risk = "high"
            decision = "unsafe_to_interpret"
        elif batch_r2 >= threshold * 0.6:
            risk = "moderate"
            decision = "interpret_with_batch_warning"
        rows.append(
            {
                "component": int(component),
                "risk": risk,
                "decision": decision,
                "max_batch_r2": batch_r2,
                "label_r2": label_r2,
            }
        )
    return pd.DataFrame(rows)


def _linear_r2(y: np.ndarray, design: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    design = np.asarray(design, dtype=float)
    mask = np.isfinite(y) & np.all(np.isfinite(design), axis=1)
    y = y[mask]
    X = design[mask]
    if y.size < 3:
        return 0.0
    X = np.column_stack([np.ones(y.shape[0]), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot <= 1e-12:
        return 0.0
    return float(np.clip(1.0 - ss_res / ss_tot, 0.0, 1.0))
