from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp


INPUT = Path("data/real/covid19_pbmc_blish_cellxgene.h5ad")
OUTPUT = Path("data/real/covid19_pbmc_blish_compact_omics_audit.h5ad")

LABEL_KEY = "Status"
DONOR_KEY = "Donor_full"
PRIMARY_CONFOUNDER_KEY = "cell_type_coarse"

KEEP_OBS = [
    "Status",
    "Donor_full",
    "Sex",
    "Admission",
    "Ventilated",
    "cell_type_coarse",
    "cell_type_fine",
    "nCount_RNA",
    "nFeature_RNA",
    "percent_mt",
]

MAX_CELLS = 12000
MAX_GENES = 3000
RANDOM_STATE = 17


def _to_bool_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin({"true", "1", "yes", "selected"})


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Missing input: {INPUT}")

    print(f"Reading {INPUT}")
    adata = ad.read_h5ad(INPUT)

    print("Original shape:", adata.shape)
    print("Layers present:", list(adata.layers.keys()))

    # Keep only cells with usable labels and donors.
    obs = adata.obs.copy()
    mask = (
        obs[LABEL_KEY].astype(str).isin(["COVID", "Healthy"])
        & obs[DONOR_KEY].astype(str).notna()
        & (obs[DONOR_KEY].astype(str) != "nan")
        & obs[PRIMARY_CONFOUNDER_KEY].astype(str).notna()
    )
    adata = adata[mask].copy()
    print("After metadata filter:", adata.shape)

    # Balanced-ish sample across Status x Donor to avoid one donor/status dominating.
    rng = np.random.default_rng(RANDOM_STATE)
    obs = adata.obs.copy()
    obs["_idx"] = np.arange(adata.n_obs)

    groups = []
    group_cols = [LABEL_KEY, DONOR_KEY]
    per_group = max(50, MAX_CELLS // max(obs.groupby(group_cols, observed=True).ngroups, 1))

    for _, g in obs.groupby(group_cols, observed=True):
        idx = g["_idx"].to_numpy()
        if len(idx) > per_group:
            idx = rng.choice(idx, size=per_group, replace=False)
        groups.append(idx)

    chosen = np.concatenate(groups)
    if len(chosen) > MAX_CELLS:
        chosen = rng.choice(chosen, size=MAX_CELLS, replace=False)

    chosen = np.sort(chosen)
    adata = adata[chosen].copy()
    print("After balanced cell subset:", adata.shape)

    # Select genes. Prefer provided Selected flag if available, otherwise top variable by stored variance.
    var = adata.var.copy()
    if "Selected" in var.columns and _to_bool_series(var["Selected"]).sum() >= 500:
        gene_mask = _to_bool_series(var["Selected"]).to_numpy()
        gene_idx = np.where(gene_mask)[0]
        print("Using var['Selected'] genes:", len(gene_idx))
    elif "sct_residual_variance" in var.columns:
        vals = pd.to_numeric(var["sct_residual_variance"], errors="coerce").fillna(0).to_numpy()
        gene_idx = np.argsort(vals)[-MAX_GENES:]
        print("Using top sct_residual_variance genes:", len(gene_idx))
    elif "sct_variance" in var.columns:
        vals = pd.to_numeric(var["sct_variance"], errors="coerce").fillna(0).to_numpy()
        gene_idx = np.argsort(vals)[-MAX_GENES:]
        print("Using top sct_variance genes:", len(gene_idx))
    else:
        gene_idx = np.arange(min(MAX_GENES, adata.n_vars))
        print("Using first genes:", len(gene_idx))

    if len(gene_idx) > MAX_GENES:
        gene_idx = gene_idx[:MAX_GENES]

    adata = adata[:, np.sort(gene_idx)].copy()
    print("After gene subset:", adata.shape)

    # Build a slim AnnData: X + selected obs + var only. No layers, no raw, no heavy uns.
    X = adata.X
    if not sp.issparse(X):
        X = sp.csr_matrix(X)
    else:
        X = X.tocsr()

    keep_obs = [c for c in KEEP_OBS if c in adata.obs.columns]
    slim = ad.AnnData(
        X=X,
        obs=adata.obs[keep_obs].copy(),
        var=adata.var.copy(),
    )

    slim.layers.clear()
    slim.uns.clear()
    slim.obsm.clear()
    slim.varm.clear()
    slim.raw = None

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    slim.write_h5ad(OUTPUT, compression="gzip")

    print("Wrote:", OUTPUT)
    print("Final shape:", slim.shape)
    print("OBS columns:", list(slim.obs.columns))

    print("\nPrimary audit command:")
    print(
        ".venv/bin/omicstrust audit "
        f"{OUTPUT} "
        "--batch-key cell_type_coarse "
        "--donor-key Donor_full "
        "--label-key Status "
        "--output results/public_covid19_pbmc_celltype_confounding_audit "
        "--config configs/worth_publication_grade.yaml"
    )

    print("\nSecondary demographic stress audit:")
    print(
        ".venv/bin/omicstrust audit "
        f"{OUTPUT} "
        "--batch-key Sex "
        "--donor-key Donor_full "
        "--label-key Status "
        "--output results/public_covid19_pbmc_sex_confounding_audit "
        "--config configs/worth_publication_grade.yaml"
    )


if __name__ == "__main__":
    main()
