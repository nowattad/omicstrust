from __future__ import annotations

import pandas as pd

from omicstrust.observability.qc_metrics import cramers_v


def pairwise_categorical_confounding(obs: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows = []
    available = [k for k in keys if k in obs.columns]
    for i, left in enumerate(available):
        for right in available[i + 1 :]:
            rows.append({"left": left, "right": right, "cramers_v": cramers_v(obs[left], obs[right])})
    return pd.DataFrame(rows)
