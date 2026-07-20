from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np
import scipy.sparse as sp


INPUT = Path("data/real/covid19_pbmc_blish_compact_omics_audit.h5ad")
OUTDIR = Path("data/real/covid19_celltype_subsets")

CELL_TYPES = [
    "CD14 Monocyte",
    "CD8 T",
    "CD4 T",
    "B",
    "NK",
]

MAX_CELLS_PER_TYPE = 6000
RANDOM_STATE = 19


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Missing compact input: {INPUT}")

    OUTDIR.mkdir(parents=True, exist_ok=True)

    adata = ad.read_h5ad(INPUT)
    rng = np.random.default_rng(RANDOM_STATE)

    print("Input shape:", adata.shape)
    print("Available cell types:")
    print(adata.obs["cell_type_coarse"].value_counts())

    for ct in CELL_TYPES:
        mask = adata.obs["cell_type_coarse"].astype(str) == ct
        sub = adata[mask].copy()

        if sub.n_obs < 300:
            print(f"Skipping {ct}: too few cells ({sub.n_obs})")
            continue

        if sub.n_obs > MAX_CELLS_PER_TYPE:
            idx = rng.choice(sub.n_obs, size=MAX_CELLS_PER_TYPE, replace=False)
            sub = sub[np.sort(idx)].copy()

        # Keep slim object.
        X = sub.X.tocsr() if sp.issparse(sub.X) else sp.csr_matrix(sub.X)
        sub = ad.AnnData(
            X=X,
            obs=sub.obs.copy(),
            var=sub.var.copy(),
        )
        sub.layers.clear()
        sub.uns.clear()
        sub.obsm.clear()
        sub.varm.clear()
        sub.raw = None

        safe_name = ct.replace(" ", "_").replace("/", "_")
        out = OUTDIR / f"covid19_{safe_name}.h5ad"
        sub.write_h5ad(out, compression="gzip")

        print("\nWrote:", out)
        print("Shape:", sub.shape)
        print("Status counts:")
        print(sub.obs["Status"].value_counts())
        print("Donor counts:")
        print(sub.obs["Donor_full"].value_counts().head())

        print("Audit command:")
        print(
            ".venv/bin/omicstrust audit "
            f"{out} "
            "--batch-key Sex "
            "--donor-key Donor_full "
            "--label-key Status "
            f"--output results/covid19_{safe_name}_within_celltype_audit "
            "--config configs/worth_publication_grade.yaml"
        )


if __name__ == "__main__":
    main()
