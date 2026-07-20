from __future__ import annotations

from omicstrust.baselines.pca import run_pca_baseline


def run_truncated_svd_baseline(X, obs=None, batch_key: str | None = None, n_components: int = 20):
    result = run_pca_baseline(X, obs=obs, batch_key=batch_key, n_components=n_components)
    result["method"] = "TruncatedSVD"
    return result
