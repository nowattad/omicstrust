import numpy as np
from scipy import sparse

from omicstrust.preprocessing.hvg_selection import (
    column_variance,
    highly_variable_gene_mask,
    select_highly_variable_genes,
)


def test_hvg_sparse_matrix_remains_sparse():
    rng = np.random.default_rng(0)
    X = sparse.random(
        500,
        3000,
        density=0.01,
        format="csr",
        random_state=0,
        data_rvs=lambda n: rng.poisson(1.5, size=n).astype(float),
    )

    X_hvg, mask = select_highly_variable_genes(X, n_top_genes=200)

    assert sparse.issparse(X_hvg)
    assert X_hvg.shape == (500, 200)
    assert mask.dtype == bool
    assert int(mask.sum()) == 200


def test_hvg_dense_chunked_variance_matches_numpy():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(100, 50))

    got = column_variance(X, chunk_size=17)
    expected = np.var(X, axis=0)

    np.testing.assert_allclose(got, expected, rtol=1e-10, atol=1e-10)


def test_hvg_is_deterministic_with_ties():
    X = np.ones((20, 10), dtype=float)

    mask1 = highly_variable_gene_mask(X, n_top_genes=3)
    mask2 = highly_variable_gene_mask(X, n_top_genes=3)

    np.testing.assert_array_equal(mask1, mask2)
    assert list(np.where(mask1)[0]) == [0, 1, 2]


def test_hvg_n_top_larger_than_features_is_safe():
    X = np.random.default_rng(2).normal(size=(30, 12))

    X_hvg, mask = select_highly_variable_genes(X, n_top_genes=100)

    assert X_hvg.shape == (30, 12)
    assert int(mask.sum()) == 12
