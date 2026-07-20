from __future__ import annotations

import argparse
from pathlib import Path

import anndata as ad
import numpy as np


LABEL_KEYWORDS = [
    "disease", "covid", "severity", "condition", "status", "infection",
    "diagnosis", "phenotype", "group", "label", "outcome", "response"
]

BATCH_KEYWORDS = [
    "batch", "site", "center", "centre", "study", "protocol", "assay",
    "technology", "platform", "chemistry", "library", "lane", "chip",
    "well", "pool", "sample"
]

DONOR_KEYWORDS = [
    "donor", "patient", "subject", "individual", "participant", "person"
]


def _safe_nunique(s):
    try:
        return int(s.astype(str).replace("nan", np.nan).nunique(dropna=True))
    except Exception:
        return 0


def _examples(s, limit=8):
    vals = []
    for x in s.astype(str).dropna().unique().tolist():
        if x.lower() not in {"nan", "none", ""}:
            vals.append(x)
        if len(vals) >= limit:
            break
    return vals


def _score_column(name: str, n_unique: int, keywords: list[str], kind: str) -> int:
    low = name.lower()
    score = 0

    for kw in keywords:
        if kw in low:
            score += 10

    if kind == "label":
        if 2 <= n_unique <= 20:
            score += 8
        elif 21 <= n_unique <= 80:
            score += 2
        else:
            score -= 5

    if kind == "batch":
        if 2 <= n_unique <= 100:
            score += 6
        elif 101 <= n_unique <= 1000:
            score += 2
        else:
            score -= 2

    if kind == "donor":
        if 3 <= n_unique <= 1000:
            score += 8
        elif n_unique > 1000:
            score -= 4

    return score


def _rank(obs, keywords, kind):
    rows = []
    for col in obs.columns:
        n_unique = _safe_nunique(obs[col])
        if n_unique < 2:
            continue

        score = _score_column(col, n_unique, keywords, kind)
        if score > 0:
            rows.append(
                {
                    "column": col,
                    "n_unique": n_unique,
                    "score": score,
                    "examples": _examples(obs[col]),
                }
            )

    rows.sort(key=lambda x: (-x["score"], x["n_unique"], x["column"]))
    return rows


def _choose_distinct(label_rows, batch_rows, donor_rows):
    label = label_rows[0]["column"] if label_rows else None

    batch = None
    for row in batch_rows:
        if row["column"] != label:
            batch = row["column"]
            break

    donor = None
    for row in donor_rows:
        if row["column"] not in {label, batch}:
            donor = row["column"]
            break

    return label, batch, donor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_h5ad")
    parser.add_argument("--max-cells", type=int, default=80000)
    parser.add_argument("--output", default="data/real/public_omics_audit_subset.h5ad")
    args = parser.parse_args()

    path = Path(args.input_h5ad)
    print(f"Reading: {path}")
    adata = ad.read_h5ad(path)

    print("\nShape:")
    print(f"  cells = {adata.n_obs}")
    print(f"  genes = {adata.n_vars}")

    print("\nOBS columns:")
    for col in adata.obs.columns:
        n = _safe_nunique(adata.obs[col])
        ex = _examples(adata.obs[col], limit=5)
        print(f"  - {col} | n_unique={n} | examples={ex}")

    label_rows = _rank(adata.obs, LABEL_KEYWORDS, "label")
    batch_rows = _rank(adata.obs, BATCH_KEYWORDS, "batch")
    donor_rows = _rank(adata.obs, DONOR_KEYWORDS, "donor")

    print("\nTop label candidates:")
    for row in label_rows[:10]:
        print(row)

    print("\nTop batch candidates:")
    for row in batch_rows[:10]:
        print(row)

    print("\nTop donor candidates:")
    for row in donor_rows[:10]:
        print(row)

    label, batch, donor = _choose_distinct(label_rows, batch_rows, donor_rows)

    print("\nChosen keys:")
    print(f"  label_key = {label}")
    print(f"  batch_key = {batch}")
    print(f"  donor_key = {donor}")

    if label is None or batch is None:
        raise SystemExit(
            "Could not auto-select enough metadata. Send the OBS columns output."
        )

    if adata.n_obs > args.max_cells:
        rng = np.random.default_rng(17)
        idx = rng.choice(adata.n_obs, size=args.max_cells, replace=False)
        adata = adata[idx].copy()
        print(f"\nDownsampled to {adata.n_obs} cells for first audit.")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out)
    print(f"\nPrepared file: {out}")

    print("\nRun this audit command:")
    cmd = [
        ".venv/bin/omicstrust audit",
        str(out),
        f"--batch-key {batch}",
        f"--label-key {label}",
    ]
    if donor is not None:
        cmd.append(f"--donor-key {donor}")
    cmd += [
        "--output results/public_covid19_pbmc_audit",
        "--config configs/worth_publication_grade.yaml",
    ]
    print(" \\\n  ".join(cmd))

    print("\nThen run the biomarker certificate:")
    print(
        ".venv/bin/python examples/no_safe_biomarker_certificate.py "
        "results/public_covid19_pbmc_audit "
        "--output results/public_covid19_pbmc_biomarker_certificate"
    )


if __name__ == "__main__":
    main()
