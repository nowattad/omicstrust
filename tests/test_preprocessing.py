from __future__ import annotations

import numpy as np

from omicstrust.preprocessing import preprocess_with_audit
from omicstrust.preprocessing.hvg_selection import highly_variable_gene_mask


def test_preprocessing_records_history():
    X = np.abs(np.arange(30, dtype=float).reshape(6, 5)) + 1
    out, _, audit = preprocess_with_audit(X, {"enabled": True, "normalize_total": True, "log1p": True, "hvg_selection": True, "n_top_genes": 3, "scale": True})
    assert out.shape == (6, 3)
    assert [h["step"] for h in audit["preprocessing_history"]] == ["normalize_total", "log1p", "hvg_selection", "zscore"]


def test_hvg_sparse_safe():
    from scipy import sparse

    X = sparse.random(100, 1000, density=0.01, format="coo", random_state=0)
    mask = highly_variable_gene_mask(X, n_top_genes=25)
    assert mask.shape == (1000,)
    assert mask.sum() == 25


def test_preprocessing_sparse_coo_after_normalization():
    from scipy import sparse

    X = sparse.random(30, 100, density=0.05, format="coo", random_state=1)
    out, _, audit = preprocess_with_audit(
        X,
        {"enabled": True, "normalize_total": True, "log1p": True, "hvg_selection": True, "n_top_genes": 20, "scale": False},
    )
    assert out.shape == (30, 20)
    assert audit["preprocessing_history"][-1]["step"] == "hvg_selection"
