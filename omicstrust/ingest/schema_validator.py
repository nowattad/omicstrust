from __future__ import annotations

from omicstrust.dataset import OmicsDataset
from omicstrust.utils.validation import ensure_2d_matrix


def validate_dataset(dataset: OmicsDataset) -> list[str]:
    warnings: list[str] = []
    ensure_2d_matrix(dataset.X)
    n_cells, n_features = dataset.X.shape
    if dataset.obs is not None and len(dataset.obs) != n_cells:
        raise ValueError("obs must have one row per cell.")
    if dataset.var is not None and len(dataset.var) != n_features:
        raise ValueError("var must have one row per feature.")
    if n_cells < 2:
        warnings.append("Dataset has fewer than two cells.")
    if n_features < 2:
        warnings.append("Dataset has fewer than two features.")
    return warnings
