from __future__ import annotations

import numpy as np
import pandas as pd

from omicstrust.ingest import fingerprint_matrix, load_dataset


def test_load_synthetic_anndata(tmp_path):
    import anndata as ad

    path = tmp_path / "tiny.h5ad"
    ad.AnnData(X=np.ones((5, 3)), obs=pd.DataFrame(index=[f"c{i}" for i in range(5)]), var=pd.DataFrame(index=[f"g{i}" for i in range(3)])).write_h5ad(path)
    dataset = load_dataset(path)
    assert dataset.shape == (5, 3)
    assert dataset.fingerprint


def test_load_dense_matrix_and_fingerprint_stable():
    X = np.arange(12).reshape(4, 3)
    a = load_dataset(X)
    b = load_dataset(X.copy())
    assert a.shape == (4, 3)
    assert fingerprint_matrix(a.X) == fingerprint_matrix(b.X)


def test_load_sparse_matrix():
    from scipy import sparse

    dataset = load_dataset(sparse.csr_matrix(np.eye(4)))
    assert dataset.metadata["sparse"] is True
