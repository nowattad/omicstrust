from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from omicstrust.utils.random import rng_from_seed, stable_seed_sequence


class EmpiricalNull:
    def __init__(
        self,
        method: str = "permutation",
        n_permutations: int = 100,
        quantile: float = 0.95,
        random_state: int = 0,
        n_jobs: int = 1,
    ):
        self.method = method
        self.n_permutations = int(n_permutations)
        self.quantile = float(quantile)
        self.random_state = int(random_state)
        self.n_jobs = int(n_jobs)
        self.null_spectra_: np.ndarray | None = None
        self.thresholds_: np.ndarray | None = None
        self.warnings_: list[str] = []

    def fit(self, X, engine_factory: Callable[[], Any], batch=None, labels=None):
        if self.n_permutations < 5:
            self.warnings_.append("Fewer than five permutations gives an underpowered empirical null.")
        matrix = X.tocsr() if sparse.issparse(X) else np.asarray(X)
        seeds = stable_seed_sequence(self.random_state, max(self.n_permutations, 1))
        spectra = []
        for seed in seeds:
            permuted = self._permuted_matrix(matrix, seed=seed, batch=batch, labels=labels)
            engine = engine_factory()
            engine.fit(permuted)
            spectra.append(engine.spectrum())
        max_len = max(len(s) for s in spectra) if spectra else 0
        padded = np.full((len(spectra), max_len), np.nan, dtype=float)
        for i, spectrum in enumerate(spectra):
            padded[i, : len(spectrum)] = spectrum
        self.null_spectra_ = padded
        self.thresholds_ = np.nanquantile(padded, self.quantile, axis=0)
        return self

    def thresholds(self) -> np.ndarray:
        self._require_fit()
        return self.thresholds_.copy()  # type: ignore[union-attr]

    def p_values(self, observed_eigenvalues) -> np.ndarray:
        self._require_fit()
        observed = np.asarray(observed_eigenvalues, dtype=float)
        null = self.null_spectra_[:, : observed.size]  # type: ignore[index]
        pvals = []
        for j, value in enumerate(observed):
            col = null[:, j]
            col = col[np.isfinite(col)]
            if col.size == 0:
                pvals.append(1.0)
            else:
                pvals.append(float((1 + np.sum(col >= value)) / (col.size + 1)))
        return np.asarray(pvals, dtype=float)

    def summary(self, observed_eigenvalues=None) -> dict[str, Any]:
        self._require_fit()
        null = self.null_spectra_  # type: ignore[assignment]
        result = {
            "method": self.method,
            "n_permutations": self.n_permutations,
            "quantile": self.quantile,
            "null_median": np.nanmedian(null, axis=0),
            "null_threshold": self.thresholds_,
            "warnings": list(self.warnings_),
        }
        if observed_eigenvalues is not None:
            observed = np.asarray(observed_eigenvalues, dtype=float)
            thresholds = self.thresholds_[: observed.size]  # type: ignore[index]
            result["empirical_p_values"] = self.p_values(observed)
            result["components_above_null"] = (observed > thresholds).tolist()
            result["n_components_above_null"] = int(np.sum(observed > thresholds))
        return result

    def _permuted_matrix(self, matrix, *, seed: int, batch=None, labels=None):
        rng = rng_from_seed(seed)
        method = self.method.lower()
        if sparse.issparse(matrix):
            return self._permuted_sparse_matrix(matrix, rng=rng, method=method, batch=batch, labels=labels)
        out = np.array(matrix, copy=True)
        if method in {"permutation", "global_permutation"}:
            return _global_feature_permutation(out, rng)
        if method in {"within_batch_permutation", "batch_aware", "batch_aware_null"}:
            if batch is None:
                self.warnings_.append("Batch-aware null requested without batch labels; using global permutation.")
                return _global_feature_permutation(out, rng)
            raw_batch = pd.Series(batch)
            batch_series = raw_batch.astype("object").where(raw_batch.notna(), "__missing__").to_numpy()
            for level in np.unique(batch_series):
                idx = np.flatnonzero(batch_series == level)
                if idx.size <= 1:
                    continue
                for j in range(out.shape[1]):
                    out[idx, j] = rng.permutation(out[idx, j])
            return out
        if method in {"label_shuffle", "label_shuffle_null"}:
            if labels is None:
                self.warnings_.append("Label-shuffle null requested without labels; using global permutation.")
            row_order = rng.permutation(out.shape[0])
            return out[row_order, :]
        if method in {"residual_bootstrap", "empty_droplet"}:
            raise NotImplementedError(
                f"Empirical null method {self.method!r} needs study-specific covariates or controls and is not in the core path."
            )
        raise ValueError(f"Unknown empirical null method: {self.method}")

    def _permuted_sparse_matrix(self, X, *, rng: np.random.Generator, method: str, batch=None, labels=None):
        if method in {"permutation", "global_permutation"}:
            return _sparse_global_feature_permutation(X, rng)
        if method in {"within_batch_permutation", "batch_aware", "batch_aware_null"}:
            if batch is None:
                self.warnings_.append("Batch-aware null requested without batch labels; using global permutation.")
                return _sparse_global_feature_permutation(X, rng)
            return _sparse_within_batch_feature_permutation(X, rng, batch)
        if method in {"label_shuffle", "label_shuffle_null"}:
            row_order = rng.permutation(X.shape[0])
            return X[row_order, :]
        if method in {"residual_bootstrap", "empty_droplet"}:
            raise NotImplementedError(
                f"Empirical null method {self.method!r} needs study-specific covariates or controls and is not in the core path."
            )
        raise ValueError(f"Unknown empirical null method: {self.method}")

    def _require_fit(self) -> None:
        if self.null_spectra_ is None or self.thresholds_ is None:
            raise RuntimeError("EmpiricalNull has not been fit.")


def _global_feature_permutation(out: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    for j in range(out.shape[1]):
        out[:, j] = rng.permutation(out[:, j])
    return out


def _sparse_global_feature_permutation(X, rng: np.random.Generator):
    X_csc = X.tocsc()
    n_rows, n_cols = X_csc.shape
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    data: list[np.ndarray] = []
    for col in range(n_cols):
        start, end = X_csc.indptr[col], X_csc.indptr[col + 1]
        values = X_csc.data[start:end]
        if values.size == 0:
            continue
        new_rows = rng.choice(n_rows, size=values.size, replace=False)
        rows.append(new_rows)
        cols.append(np.full(values.size, col, dtype=int))
        data.append(values.copy())
    return _coo_from_parts(rows, cols, data, X_csc.shape)


def _sparse_within_batch_feature_permutation(X, rng: np.random.Generator, batch):
    X_csc = X.tocsc()
    n_cols = X_csc.shape[1]
    batch_series = pd.Series(batch).astype("object").where(pd.Series(batch).notna(), "__missing__").to_numpy()
    batch_to_rows = {level: np.flatnonzero(batch_series == level) for level in np.unique(batch_series)}
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    data: list[np.ndarray] = []
    for col in range(n_cols):
        start, end = X_csc.indptr[col], X_csc.indptr[col + 1]
        col_rows = X_csc.indices[start:end]
        col_values = X_csc.data[start:end]
        if col_values.size == 0:
            continue
        col_batches = batch_series[col_rows]
        for level in np.unique(col_batches):
            mask = col_batches == level
            values = col_values[mask]
            candidates = batch_to_rows[level]
            if values.size == 0 or candidates.size == 0:
                continue
            replace = values.size > candidates.size
            new_rows = rng.choice(candidates, size=values.size, replace=replace)
            rows.append(new_rows)
            cols.append(np.full(values.size, col, dtype=int))
            data.append(values.copy())
    return _coo_from_parts(rows, cols, data, X_csc.shape)


def _coo_from_parts(rows: list[np.ndarray], cols: list[np.ndarray], data: list[np.ndarray], shape):
    if not data:
        return sparse.csr_matrix(shape)
    row = np.concatenate(rows)
    col = np.concatenate(cols)
    values = np.concatenate(data)
    return sparse.coo_matrix((values, (row, col)), shape=shape).tocsr()
