from pathlib import Path
import json
from io import StringIO
import pandas as pd

PROBES = Path("results/vanish_pc11_top_probe_loadings.csv")
MANIFEST = Path("data/real/vanish_sepsis/HumanHT-12_V4_0_R2_15002873_B.txt")

OUT = Path("results/vanish_pc11_top_probe_loadings_illumina_annotated.csv")
OUT_POS = Path("results/vanish_pc11_positive_illumina_annotated.csv")
OUT_NEG = Path("results/vanish_pc11_negative_illumina_annotated.csv")
GENES = Path("results/vanish_pc11_gene_symbols_illumina.txt")
SUMMARY = Path("results/vanish_pc11_illumina_annotation_summary.json")


def read_manifest():
    lines = MANIFEST.read_text(errors="replace").splitlines()

    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "[probes]":
            start = i + 1
            break

    if start is None:
        raise SystemExit("Could not find [Probes] section.")

    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("[") and lines[j].endswith("]"):
            end = j
            break
    if end is None:
        end = len(lines)

    df = pd.read_csv(StringIO("\n".join(lines[start:end])), sep="\t", dtype=str, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def choose_probe_column(manifest, pc11_probes):
    probe_set = set(pc11_probes)
    scores = []

    for c in manifest.columns:
        vals = manifest[c].dropna().astype(str).str.strip()
        overlap = len(set(vals).intersection(probe_set))
        starts_ilmn = int(vals.str.startswith("ILMN_").sum())
        scores.append((overlap, starts_ilmn, c))

    scores = sorted(scores, reverse=True)
    best_overlap, best_starts, best_col = scores[0]

    print("Top candidate probe columns:")
    for overlap, starts, col in scores[:15]:
        if overlap > 0 or starts > 0 or col in ["Probe_Id", "Transcript", "Array_Address_Id"]:
            print(f"{col:30s} overlap={overlap:4d} starts_ILMN={starts:6d}")

    if best_overlap == 0:
        raise SystemExit({
            "message": "No manifest column overlaps PC11 probe IDs.",
            "top_columns": scores[:10],
        })

    return best_col, best_overlap, scores


def main():
    probes = pd.read_csv(PROBES)
    probes["probe_id"] = probes["probe_id"].astype(str).str.strip()

    manifest = read_manifest()
    best_col, best_overlap, scores = choose_probe_column(manifest, probes["probe_id"].tolist())

    manifest = manifest.copy()
    manifest["probe_id"] = manifest[best_col].astype(str).str.strip()

    preferred = [
        "probe_id",
        "Symbol",
        "ILMN_Gene",
        "Entrez_Gene_ID",
        "RefSeq_ID",
        "Unigene_ID",
        "Definition",
        "Chromosome",
        "Probe_Chr_Orientation",
        "Probe_Coordinates",
        "Cytoband",
        "Probe_Sequence",
        "Probe_Id",
        "Search_Key",
        "Accession",
        "Species",
        "Source",
        "Transcript",
        "Array_Address_Id",
    ]
    cols = [c for c in preferred if c in manifest.columns]
    manifest_small = manifest[cols].drop_duplicates("probe_id")

    merged = probes.merge(manifest_small, on="probe_id", how="left")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT, index=False)
    merged.sort_values("loading", ascending=False).head(300).to_csv(OUT_POS, index=False)
    merged.sort_values("loading", ascending=True).head(300).to_csv(OUT_NEG, index=False)

    symbol_col = None
    for c in ["Symbol", "ILMN_Gene", "Search_Key"]:
        if c in merged.columns and merged[c].notna().sum() > 0:
            symbol_col = c
            break

    symbols = []
    if symbol_col:
        for val in merged[symbol_col].dropna().astype(str):
            val = val.replace("///", ";").replace(",", ";").replace(" // ", ";")
            for token in val.split(";"):
                token = token.strip()
                if token and token.lower() not in {"nan", "na", "null", "---"} and not token.startswith("ILMN_"):
                    symbols.append(token)

    seen = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    GENES.write_text("\n".join(unique))

    summary = {
        "status": "illumina_manifest_annotation_complete_v2",
        "manifest": str(MANIFEST),
        "probe_column_used": best_col,
        "overlap_with_pc11_probe_rows": int(best_overlap),
        "n_pc11_probe_rows": int(len(probes)),
        "n_manifest_rows": int(len(manifest)),
        "n_rows_with_any_annotation": int(
            merged.drop(columns=["probe_id","loading","abs_loading","probe_pc11_correlation","abs_probe_pc11_correlation"], errors="ignore")
            .notna().any(axis=1).sum()
        ),
        "n_rows_with_symbol": int(merged["Symbol"].notna().sum()) if "Symbol" in merged.columns else None,
        "symbol_column_used": symbol_col,
        "n_unique_gene_symbols": int(len(unique)),
        "top_probe_column_candidates": [
            {"column": c, "overlap": int(o), "starts_ILMN": int(s)}
            for o, s, c in scores[:10]
        ],
        "outputs": {
            "annotated_all": str(OUT),
            "positive": str(OUT_POS),
            "negative": str(OUT_NEG),
            "gene_symbols": str(GENES),
        },
    }

    SUMMARY.write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print()
    show_cols = [c for c in ["probe_id","loading","probe_pc11_correlation","Symbol","ILMN_Gene","Search_Key","Entrez_Gene_ID","RefSeq_ID","Definition"] if c in merged.columns]
    print("Top annotated rows:")
    print(merged[show_cols].head(80).to_string(index=False))


if __name__ == "__main__":
    main()
