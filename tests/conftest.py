from __future__ import annotations

from pathlib import Path

import yaml

from omicstrust.benchmarks.synthetic_generator import generate_synthetic_singlecell


def write_fast_config(path: Path) -> Path:
    config = {
        "preprocessing": {"enabled": True, "normalize_total": True, "log1p": True, "hvg_selection": True, "n_top_genes": 40, "scale": True},
        "signal": {"n_components": 5, "solver": "auto"},
        "nulls": {"enabled": True, "method": "within_batch_permutation", "n_permutations": 5, "quantile": 0.9},
        "stability": {"enabled": True, "n_bootstraps": 3, "subsample_fraction": 0.8},
        "reports": {"dpi": 80},
    }
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def synthetic_h5ad(path: Path) -> Path:
    import anndata as ad

    data = generate_synthetic_singlecell(n_cells=80, n_genes=60, rank=3, batch_strength=0.7, random_state=11)
    ad.AnnData(X=data["X"], obs=data["obs"], var=data["var"]).write_h5ad(path)
    return path
