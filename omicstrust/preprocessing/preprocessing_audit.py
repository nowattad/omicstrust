from __future__ import annotations

from typing import Any

import pandas as pd

from omicstrust.preprocessing.hvg_selection import select_highly_variable_genes
from omicstrust.preprocessing.log_transform import log1p_transform
from omicstrust.preprocessing.normalization import normalize_total
from omicstrust.preprocessing.residualization import residualize_covariates
from omicstrust.preprocessing.scaling import zscore_scale


def preprocess_with_audit(
    X,
    config: dict[str, Any],
    *,
    obs: pd.DataFrame | None = None,
    var: pd.DataFrame | None = None,
):
    history: list[dict[str, Any]] = []
    selected_var = var
    out = X
    if not config.get("enabled", False):
        return out, selected_var, {"preprocessing_history": history, "enabled": False}

    if config.get("normalize_total", False):
        target_sum = float(config.get("target_sum", 10_000.0))
        out = normalize_total(out, target_sum=target_sum)
        history.append({"step": "normalize_total", "target_sum": target_sum})
    if config.get("log1p", False):
        out = log1p_transform(out)
        history.append({"step": "log1p"})
    if config.get("hvg_selection", False):
        n_top_genes = int(config.get("n_top_genes", 2000))
        out, mask = select_highly_variable_genes(out, n_top_genes=n_top_genes)
        if selected_var is not None:
            selected_var = selected_var.loc[mask].copy()
        history.append({"step": "hvg_selection", "n_top_genes": int(mask.sum())})
    if config.get("scale", False):
        out = zscore_scale(out)
        history.append({"step": "zscore"})
    if config.get("residualize", False):
        covariates = list(config.get("covariates", []))
        out, info = residualize_covariates(out, obs if obs is not None else pd.DataFrame(), covariates)
        history.append({"step": "residualization", **info})
    return out, selected_var, {"preprocessing_history": history, "enabled": True}
