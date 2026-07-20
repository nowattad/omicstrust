from __future__ import annotations

import argparse
from pathlib import Path

from omicstrust.benchmarks.synthetic_generator import generate_synthetic_singlecell


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic single-cell AnnData file.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--n-cells", type=int, default=1000)
    parser.add_argument("--n-genes", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    try:
        import anndata as ad
    except Exception as exc:
        raise SystemExit("Generating .h5ad examples requires installing anndata.") from exc
    data = generate_synthetic_singlecell(
        n_cells=args.n_cells,
        n_genes=args.n_genes,
        rank=5,
        snr=1.0,
        dropout_rate=0.25,
        batch_strength=0.8,
        confounding_strength=0.4,
        random_state=args.random_state,
    )
    adata = ad.AnnData(X=data["X"], obs=data["obs"], var=data["var"])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
