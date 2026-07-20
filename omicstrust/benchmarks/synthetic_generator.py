from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from omicstrust.utils.random import rng_from_seed


def generate_synthetic_singlecell(
    n_cells: int = 1000,
    n_genes: int = 2000,
    rank: int = 5,
    snr: float = 1.0,
    dropout_rate: float = 0.2,
    sparsity: float = 0.5,
    batch_strength: float = 0.0,
    n_batches: int = 2,
    confounding_strength: float = 0.0,
    random_state: int = 0,
) -> dict[str, Any]:
    rng = rng_from_seed(random_state)
    rank = min(rank, n_cells, n_genes)
    U = rng.normal(size=(n_cells, rank))
    V = rng.normal(size=(rank, n_genes))
    low_rank = U @ V / np.sqrt(rank)
    noise = rng.normal(scale=1.0, size=(n_cells, n_genes))
    X = snr * low_rank + noise

    batch = rng.integers(0, n_batches, size=n_cells)
    labels = rng.integers(0, 2, size=n_cells)
    if confounding_strength > 0 and n_batches >= 2:
        flip = rng.random(n_cells) < confounding_strength
        labels[flip] = batch[flip] % 2
    if batch_strength:
        batch_loadings = rng.normal(size=(n_batches, n_genes))
        X += batch_strength * batch_loadings[batch]
    if sparsity > 0:
        sparse_loading_mask = rng.random(n_genes) < min(max(sparsity, 0.0), 1.0)
        X[:, sparse_loading_mask] += 0.5 * labels[:, None]
    X = X - X.min(axis=0, keepdims=True)
    X = np.log1p(np.exp(X))
    if dropout_rate > 0:
        dropout = rng.random(X.shape) < dropout_rate
        X[dropout] = 0.0

    obs = pd.DataFrame(
        {
            "batch": pd.Categorical([f"batch_{b}" for b in batch]),
            "donor": pd.Categorical([f"donor_{b % max(n_batches, 1)}" for b in batch]),
            "signal_label": pd.Categorical([f"label_{v}" for v in labels]),
        },
        index=[f"cell_{i}" for i in range(n_cells)],
    )
    var = pd.DataFrame(index=[f"gene_{j}" for j in range(n_genes)])
    metadata = {
        "n_cells": n_cells,
        "n_genes": n_genes,
        "rank": rank,
        "snr": snr,
        "dropout_rate": dropout_rate,
        "sparsity": sparsity,
        "batch_strength": batch_strength,
        "n_batches": n_batches,
        "confounding_strength": confounding_strength,
        "random_state": random_state,
    }
    return {
        "X": X.astype(np.float32),
        "obs": obs,
        "var": var,
        "true_factors": U,
        "true_loadings": V,
        "batch_labels": batch,
        "signal_labels": labels,
        "metadata": metadata,
    }
