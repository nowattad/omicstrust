from __future__ import annotations

from typing import Any

import numpy as np

from omicstrust.signal.covariance import weighted_covariance, weighted_mean
from omicstrust.signal.randomized_svd import randomized_svd_components
from omicstrust.signal.rank_selection import select_rank_from_spectrum
from omicstrust.signal.signal_score import explained_variance_ratio, structural_signal_score
from omicstrust.signal.spectral import eigendecompose_covariance, spectral_gap
from omicstrust.utils.validation import can_densify, finite_or_raise, is_sparse_matrix, to_dense_safe


class SSIEngine:
    def __init__(
        self,
        n_components: int = 20,
        covariance: str = "weighted",
        solver: str = "auto",
        regularization: float = 1e-8,
        random_state: int = 0,
    ):
        self.n_components = int(n_components)
        self.covariance = covariance
        self.solver = solver
        self.regularization = float(regularization)
        self.random_state = int(random_state)
        self._eigenvalues: np.ndarray | None = None
        self._components: np.ndarray | None = None
        self._scores: np.ndarray | None = None
        self._mean: np.ndarray | None = None
        self._diagnostics: dict[str, Any] = {}

    def fit(self, X, weights=None, covariates=None) -> "SSIEngine":
        if len(X.shape) != 2:
            raise ValueError("X must be a two-dimensional cells x features matrix.")
        n_cells, n_features = map(int, X.shape)
        k = min(self.n_components, n_cells, n_features)
        solver = self._choose_solver(X, n_cells, n_features)
        self._mean = weighted_mean(X, weights)

        if solver == "covariance":
            C = weighted_covariance(
                X,
                weights=weights,
                center=True,
                regularization=self.regularization,
                normalization="population",
            )
            eigenvalues, components = eigendecompose_covariance(C, k)
            dense = to_dense_safe(X, reason="SSI score projection")
            scores = (dense - self._mean) @ components.T
            condition_number = _condition_number(eigenvalues)
        elif solver == "randomized_svd":
            eigenvalues, components, scores = randomized_svd_components(X, k, random_state=self.random_state)
            condition_number = _condition_number(eigenvalues)
        else:
            raise ValueError(f"Unknown solver: {solver}")

        finite_or_raise(eigenvalues, "SSI eigenvalues")
        finite_or_raise(components, "SSI components")
        finite_or_raise(scores, "SSI scores")
        ratios = explained_variance_ratio(eigenvalues)
        self._eigenvalues = eigenvalues
        self._components = components
        self._scores = scores
        self._diagnostics = {
            "eigenvalues": eigenvalues,
            "explained_variance": ratios,
            "spectral_gaps": spectral_gap(eigenvalues),
            "selected_rank": select_rank_from_spectrum(eigenvalues),
            "condition_number": condition_number,
            "solver_used": solver,
            "n_cells": n_cells,
            "n_features": n_features,
            "signal_score": structural_signal_score(eigenvalues),
            "diagnostics": {
                "covariance": self.covariance,
                "regularization": self.regularization,
                "random_state": self.random_state,
            },
        }
        return self

    def transform(self, X):
        self._require_fit()
        dense = to_dense_safe(X, reason="SSI transform")
        return (dense - self._mean) @ self._components.T  # type: ignore[operator]

    def fit_transform(self, X, weights=None, covariates=None):
        return self.fit(X, weights=weights, covariates=covariates).scores_

    @property
    def scores_(self) -> np.ndarray:
        self._require_fit()
        return self._scores  # type: ignore[return-value]

    def spectrum(self) -> np.ndarray:
        self._require_fit()
        return self._eigenvalues.copy()  # type: ignore[union-attr]

    def components(self) -> np.ndarray:
        self._require_fit()
        return self._components.copy()  # type: ignore[union-attr]

    def diagnostics(self) -> dict[str, Any]:
        self._require_fit()
        return dict(self._diagnostics)

    def _choose_solver(self, X, n_cells: int, n_features: int) -> str:
        if self.solver in {"covariance", "randomized_svd"}:
            return self.solver
        if self.solver == "randomized":
            return "randomized_svd"
        if self.solver != "auto":
            raise ValueError("solver must be 'auto', 'covariance', or 'randomized_svd'.")
        if is_sparse_matrix(X) and not can_densify(X):
            return "randomized_svd"
        if n_features <= 2000 and can_densify(X):
            return "covariance"
        return "randomized_svd"

    def _require_fit(self) -> None:
        if self._eigenvalues is None or self._components is None or self._scores is None:
            raise RuntimeError("SSIEngine has not been fit.")


def _condition_number(values: np.ndarray) -> float | None:
    positive = np.asarray(values, dtype=float)
    positive = positive[positive > 1e-12]
    if positive.size < 2:
        return None
    return float(positive.max() / positive.min())
