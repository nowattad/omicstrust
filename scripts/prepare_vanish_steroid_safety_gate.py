from __future__ import annotations

from pathlib import Path
import json
import zipfile

import anndata as ad
import numpy as np
import pandas as pd


BASE = Path("data/real/vanish_sepsis")
SDRF = BASE / "E-MTAB-7581.sdrf.txt"
ZIP = BASE / "E-MTAB-7581.processed.1.zip"
EXTRACT_DIR = BASE / "processed_extracted"

OUT = Path("data/real/vanish_steroid_safety_gate.h5ad")
REPORT = Path("results/vanish_steroid_safety_gate_cohort_table.csv")
KEYS = Path("results/vanish_steroid_safety_gate_keys.json")


def norm_col(c: str) -> str:
    return (
        c.replace("Characteristics[", "")
        .replace("Factor Value[", "")
        .replace("Comment [", "comment_[")
        .replace("]", "")
        .replace(" ", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace("/", "_")
        .lower()
    )


def make_unique(cols):
    seen = {}
    out = []
    for c in cols:
        if c not in seen:
            seen[c] = 1
            out.append(c)
        else:
            seen[c] += 1
            out.append(f"{c}__dup{seen[c]}")
    return out


def clean(x):
    if pd.isna(x):
        return "missing"
    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "na"}:
        return "missing"
    return s


def binary_outcome(x):
    s = clean(x).lower()
    if s == "dead":
        return 1
    if s == "alive":
        return 0
    return np.nan


def yes_no_binary(x):
    s = clean(x).lower()
    if s == "yes":
        return 1
    if s == "no":
        return 0
    return np.nan


def get_col(df: pd.DataFrame, name: str, default="missing") -> pd.Series:
    # Prefer exact column, otherwise first duplicate suffix.
    candidates = [c for c in df.columns if c == name or c.startswith(name + "__dup")]
    if not candidates:
        return pd.Series(default, index=df.index)
    # Use first candidate; Characteristics and Factor Value are normally identical here.
    return df[candidates[0]].map(clean)


def get_numeric(df: pd.DataFrame, name: str) -> pd.Series:
    candidates = [c for c in df.columns if c == name or c.startswith(name + "__dup")]
    if not candidates:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[candidates[0]], errors="coerce")


def main():
    print("Reading SDRF:", SDRF)
    meta_raw = pd.read_csv(SDRF, sep="\t", dtype=str)
    meta_raw.columns = make_unique([norm_col(c) for c in meta_raw.columns])

    print("SDRF shape:", meta_raw.shape)
    print("SDRF columns:")
    print(list(meta_raw.columns))
    print()
    print("Potential duplicate-normalized treatment columns:")
    print([c for c in meta_raw.columns if "drug" in c])

    print()
    print("Extracting processed matrix:", ZIP)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP) as z:
        print("ZIP files:")
        for name in z.namelist():
            print(" ", name)
        matrix_names = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not matrix_names:
            raise SystemExit("No txt matrix found inside processed zip.")
        matrix_name = matrix_names[0]
        z.extract(matrix_name, EXTRACT_DIR)

    matrix_path = EXTRACT_DIR / matrix_name
    print("Matrix file:", matrix_path)

    # In this VANISH matrix, columns are sample IDs, rows are features/probes.
    mat = pd.read_csv(matrix_path, sep="\t", low_memory=False)

    print("Raw matrix shape:", mat.shape)
    print("First 10 matrix columns:")
    print(list(mat.columns[:10]))

    # If there is no explicit feature-id column, use row index as feature IDs.
    # Here matrix has 176 columns but 175 expression samples overlap metadata;
    # one column may be feature/probe-like or one sample missing from metadata.
    sample_ids = set(meta_raw["source_name"].astype(str)) if "source_name" in meta_raw.columns else set()

    possible_expr_cols = [str(c).strip() for c in mat.columns]
    overlap_all = sorted(set(possible_expr_cols).intersection(sample_ids))

    if len(overlap_all) >= 50:
        # No feature column; all matrix columns are samples or mostly samples.
        expr = mat.copy()
        expr.columns = possible_expr_cols
        features = [f"feature_{i+1}" for i in range(expr.shape[0])]
    else:
        # First column is feature/probe id.
        feature_col = mat.columns[0]
        features = mat[feature_col].astype(str).to_list()
        expr = mat.drop(columns=[feature_col])
        expr.columns = [str(c).strip() for c in expr.columns]

    # Make feature names unique.
    seen = {}
    unique_features = []
    for f in features:
        if f not in seen:
            seen[f] = 0
            unique_features.append(f)
        else:
            seen[f] += 1
            unique_features.append(f"{f}__dup{seen[f]}")

    # Identify sample id column in metadata.
    sample_col_candidates = ["source_name", "assay_name", "extract_name", "individual"]
    sample_col = None
    for c in sample_col_candidates:
        if c in meta_raw.columns:
            sample_col = c
            break
    if sample_col is None:
        raise SystemExit("Could not find sample column in SDRF.")

    meta_raw["audit_sample_id"] = meta_raw[sample_col].astype(str).str.strip()

    common = sorted(set(expr.columns).intersection(set(meta_raw["audit_sample_id"])))
    print()
    print("Expression columns:", len(expr.columns))
    print("Metadata samples:", meta_raw["audit_sample_id"].nunique())
    print("Common samples:", len(common))

    if len(common) < 50:
        print("Example expression columns:", list(expr.columns[:20]))
        print("Example metadata samples:", meta_raw["audit_sample_id"].head(20).tolist())
        raise SystemExit("Too few common samples. Need inspect matrix/sample IDs.")

    expr = expr[common]
    X = expr.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float).T

    if np.isnan(X).any():
        med = np.nanmedian(X, axis=0)
        med = np.nan_to_num(med, nan=0.0)
        inds = np.where(np.isnan(X))
        X[inds] = np.take(med, inds[1])

    meta = meta_raw.drop_duplicates("audit_sample_id").set_index("audit_sample_id").loc[common].copy()

    # Create audit columns.
    meta["audit_srs"] = get_col(meta, "srs").map(lambda x: f"SRS{x}" if x in {"1", "2"} else clean(x))
    meta["audit_steroid"] = get_col(meta, "drug2_per_protocol")
    meta["audit_vasopressor"] = get_col(meta, "drug1_per_protocol")
    meta["audit_outcome_28"] = get_col(meta, "outcome_day_28")
    meta["audit_death_28"] = meta["audit_outcome_28"].map(binary_outcome)

    meta["audit_age"] = get_numeric(meta, "age")
    meta["audit_sex"] = get_col(meta, "sex")
    meta["audit_apache_ii"] = get_numeric(meta, "apache_ii")

    for c in [
        "iscaemic_heart_disease",
        "copd",
        "chronic_renal_failure",
        "cirrhosis",
        "cancer",
        "immunocompromise",
        "diabetes",
    ]:
        meta[f"audit_{c}"] = get_col(meta, c).map(yes_no_binary)

    steroid_keep = meta["audit_steroid"].astype(str).isin(["Hydrocortisone", "Placebo"])
    outcome_keep = meta["audit_outcome_28"].astype(str).isin(["Alive", "Dead"])
    srs_keep = meta["audit_srs"].astype(str).isin(["SRS1", "SRS2"])

    keep = steroid_keep & outcome_keep & srs_keep

    print()
    print("Before filtering:", len(meta))
    print("drug2 counts:")
    print(meta["audit_steroid"].value_counts(dropna=False).to_string())
    print()
    print("outcome counts:")
    print(meta["audit_outcome_28"].value_counts(dropna=False).to_string())
    print()
    print("SRS counts:")
    print(meta["audit_srs"].value_counts(dropna=False).to_string())

    X = X[keep.to_numpy(), :]
    meta = meta.loc[keep].copy()

    print()
    print("After filtering Hydrocortisone/Placebo + Alive/Dead + SRS1/SRS2:", len(meta))
    print()
    print("SRS × steroid:")
    print(pd.crosstab(meta["audit_srs"], meta["audit_steroid"]).to_string())
    print()
    print("Outcome × steroid × SRS:")
    print(pd.crosstab([meta["audit_srs"], meta["audit_steroid"]], meta["audit_outcome_28"]).to_string())

    var = pd.DataFrame(index=unique_features)
    var = var.iloc[: X.shape[1]].copy()
    var["feature_id"] = var.index.astype(str)

    a = ad.AnnData(X=X, obs=meta, var=var)
    a.obs_names = meta.index.astype(str)
    a.var_names_make_unique()

    a.uns["FINAL_MEDICAL_QUESTION"] = {
        "question": "Does SRS endotype identify septic shock patients who may benefit from or be harmed by hydrocortisone?",
        "clinical_decision": "hydrocortisone vs placebo in septic shock",
        "primary_outcome": "28-day mortality",
        "key_test": "hydrocortisone × SRS interaction, audited against severity, treatment arms, age, sex, and metadata leakage",
        "source": "E-MTAB-7581 VANISH trial transcriptomics",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    a.write_h5ad(OUT)
    a.obs.to_csv(REPORT)

    keys = {
        "data": str(OUT),
        "n_patients": int(a.n_obs),
        "n_features": int(a.n_vars),
        "label_keys": {
            "srs": "audit_srs",
            "outcome": "audit_outcome_28",
            "death_binary": "audit_death_28",
            "steroid": "audit_steroid",
        },
        "confounders": [
            "audit_age",
            "audit_sex",
            "audit_apache_ii",
            "audit_vasopressor",
            "audit_steroid",
        ],
        "clinical_question": "Does hydrocortisone benefit/harm differ by SRS endotype?",
    }

    KEYS.write_text(json.dumps(keys, indent=2))

    print()
    print("Saved:", OUT)
    print(a)
    print()
    print("Saved cohort table:", REPORT)
    print("Saved keys:", KEYS)
    print(json.dumps(keys, indent=2))


if __name__ == "__main__":
    main()
