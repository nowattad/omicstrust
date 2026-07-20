from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from omicstrust.stability.subspace_stability import subspace_similarity
from omicstrust.utils.random import rng_from_seed


class StabilityAnalyzer:
    def __init__(
        self,
        n_bootstraps: int = 20,
        subsample_fraction: float = 0.8,
        random_state: int = 0,
    ):
        self.n_bootstraps = int(n_bootstraps)
        self.subsample_fraction = float(subsample_fraction)
        self.random_state = int(random_state)
        self.results_: list[dict[str, Any]] = []
        self.reference_rank_: int | None = None
        self.reference_components_: np.ndarray | None = None

    def fit(self, X, engine_factory: Callable[[], Any]):
        n_cells = int(X.shape[0])
        n_subsample = max(2, int(round(n_cells * self.subsample_fraction)))
        rng = rng_from_seed(self.random_state)
        reference = engine_factory().fit(X)
        self.reference_components_ = reference.components()
        self.reference_rank_ = int(reference.diagnostics().get("selected_rank", 0))
        self.results_ = []
        for _ in range(max(self.n_bootstraps, 1)):
            idx = rng.choice(n_cells, size=n_subsample, replace=False)
            engine = engine_factory().fit(X[idx, :])
            self.results_.append(
                {
                    "subspace_similarity": subspace_similarity(self.reference_components_, engine.components()),
                    "selected_rank": int(engine.diagnostics().get("selected_rank", 0)),
                    "eigenvalues": engine.spectrum(),
                }
            )
        return self

    def summary(self) -> dict[str, Any]:
        if not self.results_:
            return {
                "mean_subspace_similarity": 0.0,
                "rank_mode": 0,
                "rank_std": 0.0,
                "stability_status": "insufficient_information",
                "warnings": ["StabilityAnalyzer has not been fit."],
            }
        sims = np.asarray([r["subspace_similarity"] for r in self.results_], dtype=float)
        ranks = np.asarray([r["selected_rank"] for r in self.results_], dtype=int)
        rank_values, counts = np.unique(ranks, return_counts=True)
        rank_mode = int(rank_values[np.argmax(counts)])
        mean_sim = float(np.mean(sims))
        status = "high"
        warnings: list[str] = []
        if mean_sim < 0.5:
            status = "low"
            warnings.append("Bootstrap subspace similarity is low.")
        elif mean_sim < 0.7:
            status = "moderate"
            warnings.append("Bootstrap subspace similarity is moderate.")
        return {
            "mean_subspace_similarity": mean_sim,
            "subspace_similarity_values": sims,
            "rank_mode": rank_mode,
            "rank_std": float(np.std(ranks)),
            "reference_rank": self.reference_rank_,
            "stability_status": status,
            "warnings": warnings,
        }
