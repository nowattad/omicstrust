from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from omicstrust.risk.batch_effect import categorical_association_r2
from omicstrust.utils.serialization import make_json_safe


PERTURBATION_KEYS = (
    "perturbation",
    "perturbation_name",
    "guide",
    "guide_id",
    "guide_identity",
    "target",
    "target_gene",
    "gene",
    "condition",
)


def compute_perturb_report(obs: pd.DataFrame | None, scores: np.ndarray | None = None) -> dict[str, Any]:
    if obs is None or obs.empty:
        return _not_available("No observation metadata was available.")
    perturb_key = _find_perturbation_key(obs)
    if perturb_key is None:
        return _not_available("No perturbation or guide metadata column was detected.")

    labels = obs[perturb_key].astype("object").where(obs[perturb_key].notna(), "__missing__")
    counts = labels.value_counts()
    total = max(int(counts.sum()), 1)
    imbalance = float(counts.iloc[0] / total) if not counts.empty else 0.0
    rare_groups = counts[counts < 5]
    component_associations = []
    if scores is not None:
        scores_arr = np.asarray(scores, dtype=float)
        for component_idx in range(scores_arr.shape[1]):
            component_associations.append(
                {
                    "component": component_idx + 1,
                    "perturbation_r2": categorical_association_r2(scores_arr[:, component_idx], labels),
                }
            )
    max_perturbation_r2 = max([float(row["perturbation_r2"]) for row in component_associations], default=0.0)
    warnings: list[str] = []
    if imbalance >= 0.8:
        warnings.append("Perturbation labels are highly imbalanced.")
    if not rare_groups.empty:
        warnings.append(f"{len(rare_groups)} perturbation groups have fewer than five cells.")
    return make_json_safe(
        {
            "available": True,
            "perturbation_key": perturb_key,
            "n_perturbations": int(counts.shape[0]),
            "top_perturbations": counts.head(20).to_dict(),
            "imbalance_top_fraction": imbalance,
            "rare_perturbation_groups": rare_groups.head(50).to_dict(),
            "component_associations": component_associations,
            "max_perturbation_r2": max_perturbation_r2,
            "perturbation_signal_status": "detected" if max_perturbation_r2 >= 0.2 else "not_dominant",
            "warnings": warnings,
        }
    )


def _find_perturbation_key(obs: pd.DataFrame) -> str | None:
    lowered = {str(column).lower(): str(column) for column in obs.columns}
    for candidate in PERTURBATION_KEYS:
        if candidate in lowered:
            return lowered[candidate]
    for lowered_name, original in lowered.items():
        if "guide" in lowered_name or "perturb" in lowered_name:
            return original
    return None


def _not_available(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "warnings": []}
