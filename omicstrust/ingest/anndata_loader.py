from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from omicstrust.dataset import OmicsDataset
from omicstrust.ingest.fingerprint import fingerprint_input, fingerprint_matrix
from omicstrust.utils.validation import ensure_2d_matrix, is_sparse_matrix


def load_dataset(
    source: str | Path | Any,
    *,
    layer: str | None = None,
    use_raw: bool = False,
    obs: pd.DataFrame | None = None,
    var: pd.DataFrame | None = None,
) -> OmicsDataset:
    """Load supported data into an OmicsDataset.

    Paths ending in ``.h5ad`` use AnnData. CSV/TSV files are interpreted as
    cell-by-feature matrices with row IDs in the first column when present.
    Matrix-like objects are wrapped directly.
    """

    if isinstance(source, (str, Path)):
        path = Path(source).expanduser()
        if not path.exists():
            raise FileNotFoundError(
                f"Input file not found: {path}. Replace the example path with a real data file path."
            )
        suffix = path.suffix.lower()
        if suffix == ".h5ad":
            return load_h5ad(path, layer=layer, use_raw=use_raw)
        if suffix in {".csv", ".tsv", ".txt"}:
            return load_matrix_table(path)
        raise ValueError(f"Unsupported input format: {path.suffix}")

    ensure_2d_matrix(source)
    metadata = _matrix_metadata(source, input_type=type(source).__name__, loaded_layer=layer)
    return OmicsDataset(
        X=source,
        obs=obs,
        var=var,
        layers=None,
        metadata=metadata,
        source_path=None,
        fingerprint=fingerprint_matrix(source),
    )


def load_h5ad(path: str | Path, *, layer: str | None = None, use_raw: bool = False) -> OmicsDataset:
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}. Replace the example path with a real .h5ad file path."
        )
    try:
        import anndata as ad
    except Exception as exc:
        raise ImportError("Loading .h5ad files requires the optional dependency 'anndata'.") from exc

    try:
        adata = ad.read_h5ad(path)
    except OSError as exc:
        raise ValueError(f"Could not read {path} as a valid .h5ad file: {exc}") from exc
    if use_raw:
        if adata.raw is None:
            raise ValueError("use_raw=True was requested, but the AnnData object has no .raw matrix.")
        X = adata.raw.X
        var = adata.raw.var.copy()
        loaded_layer = "raw"
    elif layer:
        if layer not in adata.layers:
            raise KeyError(f"Layer {layer!r} was requested but is not present in the AnnData file.")
        X = adata.layers[layer]
        var = adata.var.copy()
        loaded_layer = layer
    else:
        X = adata.X
        var = adata.var.copy()
        loaded_layer = "X"

    ensure_2d_matrix(X)
    obs = adata.obs.copy()
    layers = {str(k): v for k, v in adata.layers.items()}
    metadata = _matrix_metadata(X, input_type="h5ad", loaded_layer=loaded_layer)
    metadata.update({"obs_columns": list(obs.columns), "var_columns": list(var.columns)})
    return OmicsDataset(
        X=X,
        obs=obs,
        var=var,
        layers=layers,
        metadata=metadata,
        source_path=str(path),
        fingerprint=fingerprint_input(path),
    )


def load_matrix_table(path: str | Path) -> OmicsDataset:
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}. Replace the example path with a real matrix table path."
        )
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    frame = pd.read_csv(path, sep=sep, index_col=0)
    X = frame.to_numpy(dtype=float)
    obs = pd.DataFrame(index=frame.index.astype(str))
    var = pd.DataFrame(index=frame.columns.astype(str))
    metadata = _matrix_metadata(X, input_type=path.suffix.lower().lstrip("."), loaded_layer="table")
    return OmicsDataset(
        X=X,
        obs=obs,
        var=var,
        layers=None,
        metadata=metadata,
        source_path=str(path),
        fingerprint=fingerprint_input(path),
    )


def _matrix_metadata(X: Any, *, input_type: str, loaded_layer: str | None) -> dict[str, Any]:
    ensure_2d_matrix(X)
    return {
        "input_type": input_type,
        "shape": [int(X.shape[0]), int(X.shape[1])],
        "n_cells": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "sparse": is_sparse_matrix(X),
        "dtype": str(getattr(X, "dtype", "unknown")),
        "loaded_layer": loaded_layer,
    }
