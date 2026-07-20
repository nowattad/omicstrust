from pathlib import Path
import json, re, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

OUT = Path("results/cross_disease_reversal_atlas")
OUT.mkdir(parents=True, exist_ok=True)

def norm_id(x):
    return re.sub(r"[^A-Z0-9]", "", str(x).upper())

def as_array(x):
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)

def zscore_values(x):
    s = pd.to_numeric(pd.Series(x), errors="coerce")
    return ((s - s.mean()) / s.std(ddof=0)).values

def pick_col(df, words):
    best, score = None, 0
    for c in df.columns:
        text = (str(c) + " " + " ".join(df[c].dropna().astype(str).head(80))).lower()
        s = sum(w in text for w in words)
        if s > score:
            best, score = c, s
    return best

def binary_outcome(s):
    vals = s.astype(str).str.lower()
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().sum() >= 10 and set(num.dropna().unique()).issubset({0, 1}):
        return num

    y = pd.Series(np.nan, index=s.index)
    y[vals.str.contains("death|dead|died|non-survivor|non survivor|yes|true", regex=True)] = 1
    y[vals.str.contains("alive|survivor|survived|no|false", regex=True)] = 0
    return y

def read_pc11_annotations():
    files = [
        Path("results/vanish_pc11_positive_illumina_annotated.csv"),
        Path("results/vanish_pc11_negative_illumina_annotated.csv"),
        Path("results/vanish_pc11_top_probe_loadings_illumina_annotated.csv"),
    ]

    rows = []
    for p in files:
        if not p.exists():
            continue
        df = pd.read_csv(p)
        probe_col = "probe_id" if "probe_id" in df.columns else "Probe_Id"
        sym_col = "Symbol" if "Symbol" in df.columns else None
        corr_col = "probe_pc11_correlation" if "probe_pc11_correlation" in df.columns else None
        loading_col = "loading" if "loading" in df.columns else None

        if sym_col is None or corr_col is None:
            continue

        for _, r in df.iterrows():
            sym = str(r[sym_col]).strip().upper()
            sym = re.split(r"[;,/| ]+", sym)[0]
            if sym in {"", "NAN", "NA", "NONE", "---"}:
                continue

            rows.append({
                "probe_id": str(r[probe_col]).strip(),
                "symbol": sym,
                "expected_corr": float(pd.to_numeric(r[corr_col], errors="coerce")),
                "loading": float(pd.to_numeric(r[loading_col], errors="coerce")) if loading_col else np.nan,
                "source_file": str(p)
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.drop_duplicates(subset=["probe_id", "symbol", "expected_corr"])

def load_pc11_for_obs(obs):
    pc_path = Path("results/vanish_denovo_vasopressin_pc_scores.csv")
    if not pc_path.exists():
        hits = list(Path(".").glob("**/vanish_denovo_vasopressin_pc_scores.csv"))
        pc_path = hits[0] if hits else None

    if not pc_path:
        return None, {"ok": False, "error": "pc_scores_file_not_found"}

    pc = pd.read_csv(pc_path)
    pc11_col = pick_col(pc, ["pc11"])
    if not pc11_col:
        return None, {"ok": False, "error": "pc11_col_not_found", "pc_columns": pc.columns.tolist()}

    obs_df = obs.copy()
    obs_df["__row__"] = np.arange(len(obs_df))

    best = None
    best_n = 0
    for oc in obs_df.columns:
        obs_ids = set(obs_df[oc].dropna().astype(str).map(norm_id))
        for pc_col in pc.columns:
            pc_ids = set(pc[pc_col].dropna().astype(str).map(norm_id))
            n = len(obs_ids & pc_ids)
            if n > best_n:
                best_n = n
                best = (oc, pc_col)

    if best and best_n >= 20:
        oc, pc_col = best
        a = obs_df[["__row__", oc]].copy()
        a["_id"] = a[oc].astype(str).map(norm_id)
        b = pc[[pc_col, pc11_col]].copy()
        b["_id"] = b[pc_col].astype(str).map(norm_id)
        merged = a.merge(b[["_id", pc11_col]], on="_id", how="left").sort_values("__row__")
        vals = pd.to_numeric(merged[pc11_col], errors="coerce").values
        return vals, {
            "ok": True,
            "mode": "id_merge",
            "obs_col": oc,
            "pc_col": pc_col,
            "n_overlap": int(best_n),
            "pc11_col": pc11_col,
            "pc_path": str(pc_path),
            "n_nonmissing": int(np.isfinite(vals).sum())
        }

    if len(pc) == len(obs_df):
        vals = pd.to_numeric(pc[pc11_col], errors="coerce").values
        return vals, {
            "ok": True,
            "mode": "row_order_equal_length",
            "pc11_col": pc11_col,
            "pc_path": str(pc_path),
            "n_nonmissing": int(np.isfinite(vals).sum())
        }

    return None, {
        "ok": False,
        "error": "could_not_merge_pc11",
        "pc_shape": list(pc.shape),
        "obs_shape": list(obs_df.shape)
    }

def feature_correlations_with_pc11(X, pc11):
    pc11 = np.asarray(pc11, dtype=float)
    ok = np.isfinite(pc11)
    X = X[ok, :]
    y = pc11[ok]
    y = y - np.nanmean(y)
    y = y / np.nanstd(y)

    Xmean = np.nanmean(X, axis=0)
    Xsd = np.nanstd(X, axis=0)
    Xsd[Xsd == 0] = np.nan
    Z = (X - Xmean) / Xsd
    return np.nanmean(Z * y[:, None], axis=0)

def match_pdia6_feature(adata, X, pc11, ann):
    targets = ann[ann["symbol"] == "PDIA6"].copy()
    if targets.empty:
        return None, {"ok": False, "error": "PDIA6_not_found_in_pc11_annotations"}

    corrs = feature_correlations_with_pc11(X, pc11)

    rows = []
    for _, r in targets.iterrows():
        expected = float(r["expected_corr"])
        diffs = np.abs(corrs - expected)
        idx = int(np.argmin(diffs))
        rows.append({
            "probe_id": r["probe_id"],
            "symbol": r["symbol"],
            "expected_corr": expected,
            "matched_feature_index0": idx,
            "matched_feature_name": str(adata.var_names[idx]),
            "observed_corr": float(corrs[idx]),
            "abs_diff": float(diffs[idx]),
            "loading": None if pd.isna(r["loading"]) else float(r["loading"]),
            "source_file": r["source_file"]
        })

    m = pd.DataFrame(rows).sort_values("abs_diff")
    best = m.iloc[0].to_dict()
    validated = bool(best["abs_diff"] <= 1e-6)

    return int(best["matched_feature_index0"]), {
        "ok": validated,
        "all_pdia6_matches": rows,
        "best_match": best,
        "validation_rule": "abs_diff <= 1e-6"
    }

def logit_fit_lrt(df, y_col, full_cols, reduced_cols):
    try:
        import statsmodels.api as sm
        from scipy.stats import chi2
    except Exception as e:
        return {"ok": False, "error": f"missing_package:{e}"}

    cols = [y_col] + list(dict.fromkeys(full_cols + reduced_cols))
    d = df[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()

    if len(d) < 20 or d[y_col].nunique() < 2:
        return {"ok": False, "error": "insufficient_data", "n": int(len(d)), "counts": d[y_col].value_counts(dropna=False).to_dict()}

    y = pd.to_numeric(d[y_col], errors="coerce")

    def Xmat(cols):
        if not cols:
            return sm.add_constant(pd.DataFrame(index=d.index), has_constant="add")
        x = d[cols].apply(pd.to_numeric, errors="coerce")
        x = x.fillna(x.median(numeric_only=True))
        return sm.add_constant(x, has_constant="add")

    try:
        full = sm.Logit(y, Xmat(full_cols)).fit(disp=False, maxiter=250)
        red = sm.Logit(y, Xmat(reduced_cols)).fit(disp=False, maxiter=250)

        lrt = float(2 * (full.llf - red.llf))
        p = float(chi2.sf(lrt, len(full_cols) - len(reduced_cols)))

        return {
            "ok": True,
            "n": int(len(d)),
            "counts": d[y_col].value_counts().to_dict(),
            "lrt": lrt,
            "lrt_p": p,
            "params": {k: float(v) for k, v in full.params.to_dict().items()},
            "pvalues": {k: float(v) for k, v in full.pvalues.to_dict().items()}
        }
    except Exception as e:
        return {"ok": False, "error": f"logit_failed:{e}", "n": int(len(d))}

def permutation_interaction(df, score_col, int_col, covars, n_perm=500, seed=44):
    observed = logit_fit_lrt(
        df,
        "death_y",
        [score_col, "vasopressin_bin", int_col] + covars,
        [score_col, "vasopressin_bin"] + covars
    )
    if not observed.get("ok"):
        return observed

    rng = np.random.default_rng(seed)
    obs_lrt = observed["lrt"]
    ge, okn = 0, 0

    base = df.copy()
    for _ in range(n_perm):
        d = base.copy()

        # shuffle score within vasopressor arms
        for arm in sorted(d["vasopressin_bin"].dropna().unique()):
            idx = d.index[d["vasopressin_bin"] == arm]
            d.loc[idx, score_col] = rng.permutation(d.loc[idx, score_col].values)

        d[int_col] = d[score_col] * d["vasopressin_bin"]

        fit = logit_fit_lrt(
            d,
            "death_y",
            [score_col, "vasopressin_bin", int_col] + covars,
            [score_col, "vasopressin_bin"] + covars
        )
        if fit.get("ok"):
            ge += int(fit["lrt"] >= obs_lrt)
            okn += 1

    observed["permutation_p_within_treatment_arms"] = None if okn == 0 else float((ge + 1) / (okn + 1))
    observed["n_permutations_ok"] = okn
    return observed

def bootstrap_interaction(df, score_col, int_col, covars, n_boot=500, seed=55):
    try:
        import statsmodels.api as sm
    except Exception as e:
        return {"ok": False, "error": f"missing_statsmodels:{e}"}

    cols = ["death_y", score_col, "vasopressin_bin", int_col] + covars
    d0 = df[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if len(d0) < 20:
        return {"ok": False, "error": "too_few_rows", "n": int(len(d0))}

    rng = np.random.default_rng(seed)
    betas = []

    def fit_beta(d):
        y = pd.to_numeric(d["death_y"], errors="coerce")
        X = d[[score_col, "vasopressin_bin", int_col] + covars].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(X.median(numeric_only=True))
        X = sm.add_constant(X, has_constant="add")
        fit = sm.Logit(y, X).fit(disp=False, maxiter=200)
        return float(fit.params[int_col])

    for _ in range(n_boot):
        try:
            idx = rng.integers(0, len(d0), len(d0))
            b = fit_beta(d0.iloc[idx].copy())
            if np.isfinite(b):
                betas.append(b)
        except Exception:
            pass

    if not betas:
        return {"ok": False, "error": "no_bootstrap_fits"}

    betas = np.asarray(betas)
    obs = logit_fit_lrt(
        d0,
        "death_y",
        [score_col, "vasopressin_bin", int_col] + covars,
        [score_col, "vasopressin_bin"] + covars
    )
    obs_beta = obs.get("params", {}).get(int_col)

    return {
        "ok": True,
        "n_boot_ok": int(len(betas)),
        "observed_beta": obs_beta,
        "median_beta": float(np.median(betas)),
        "ci95_low": float(np.quantile(betas, 0.025)),
        "ci95_high": float(np.quantile(betas, 0.975)),
        "fraction_same_sign_as_observed": None if obs_beta is None else float(np.mean(np.sign(betas) == np.sign(obs_beta)))
    }

def leave_one_out(df, score_col, int_col, covars):
    betas, pvals = [], []
    for i in range(len(df)):
        d = df.drop(df.index[i]).copy()
        fit = logit_fit_lrt(
            d,
            "death_y",
            [score_col, "vasopressin_bin", int_col] + covars,
            [score_col, "vasopressin_bin"] + covars
        )
        if fit.get("ok"):
            betas.append(fit["params"].get(int_col))
            pvals.append(fit.get("pvalues", {}).get(int_col))

    betas = np.asarray([b for b in betas if b is not None and np.isfinite(b)])
    pvals = np.asarray([p for p in pvals if p is not None and np.isfinite(p)])

    if len(betas) == 0:
        return {"ok": False, "error": "no_loo_fits"}

    return {
        "ok": True,
        "n_loo_ok": int(len(betas)),
        "beta_median": float(np.median(betas)),
        "beta_min": float(np.min(betas)),
        "beta_max": float(np.max(betas)),
        "fraction_beta_negative": float(np.mean(betas < 0)),
        "p_median": None if len(pvals) == 0 else float(np.median(pvals)),
        "fraction_p_lt_0_05": None if len(pvals) == 0 else float(np.mean(pvals < 0.05))
    }

def mortality_table(df, score_col):
    d = df[["death_y", "vasopressin_bin", score_col]].dropna().copy()
    d["score_group"] = np.where(d[score_col] >= d[score_col].median(), "high", "low")

    rows = []
    for grp in ["low", "high"]:
        for arm in [0, 1]:
            x = d[(d["score_group"] == grp) & (d["vasopressin_bin"] == arm)]
            rows.append({
                "score_group": grp,
                "vasopressin_bin": arm,
                "n": int(len(x)),
                "deaths": int(x["death_y"].sum()) if len(x) else 0,
                "mortality": None if len(x) == 0 else float(x["death_y"].mean())
            })
    return rows

result = {
    "test": "PDIA6 independence + bootstrap validation v8",
    "question": "Does PDIA6 reproduce VasoGate, and does it add information beyond PC11?",
    "ruo_note": "Research-use only; not diagnostic or treatment guidance."
}

try:
    import anndata as ad
except Exception as e:
    result.update({"ok": False, "error": f"anndata_not_available:{e}"})
else:
    h5ad_path = Path("data/real/vanish_steroid_safety_gate.h5ad")
    if not h5ad_path.exists():
        result.update({"ok": False, "error": "missing_h5ad"})
    else:
        adata = ad.read_h5ad(h5ad_path)
        X = as_array(adata.X)
        obs = adata.obs.copy()
        obs["sample_id"] = obs.index.astype(str)

        ann = read_pc11_annotations()
        pc11, pc11_info = load_pc11_for_obs(obs)
        pdia6_idx, pdia6_match = match_pdia6_feature(adata, X, pc11, ann)

        result["adata_shape"] = list(adata.shape)
        result["pc11_merge_info"] = pc11_info
        result["pdia6_match"] = pdia6_match

        if pc11 is None or pdia6_idx is None or not pdia6_match.get("ok"):
            result.update({"ok": False, "error": "pc11_or_pdia6_mapping_failed"})
        else:
            df = obs.copy()

            df["PC11_z"] = zscore_values(pc11)
            df["PDIA6_z"] = zscore_values(X[:, pdia6_idx])

            death_col = "audit_death_28" if "audit_death_28" in df.columns else "outcome_day_28"
            vaso_col = "audit_vasopressor" if "audit_vasopressor" in df.columns else "drug1_per_protocol"
            steroid_col = "audit_steroid" if "audit_steroid" in df.columns else None
            srs_col = "audit_srs" if "audit_srs" in df.columns else "srs"

            df["death_y"] = binary_outcome(df[death_col])
            df["vasopressin_bin"] = df[vaso_col].astype(str).str.lower().str.contains("vasopressin").astype(int)

            df["PC11_x_vaso"] = df["PC11_z"] * df["vasopressin_bin"]
            df["PDIA6_x_vaso"] = df["PDIA6_z"] * df["vasopressin_bin"]

            covars_core = []
            if steroid_col:
                df["steroid_bin"] = df[steroid_col].astype(str).str.lower().str.contains("hydro|steroid").astype(int)
                covars_core.append("steroid_bin")
            if srs_col:
                df["srs2_bin"] = df[srs_col].astype(str).str.lower().str.contains("srs2|group 2|2").astype(int)
                covars_core.append("srs2_bin")

            covars_clinical = list(covars_core)

            age_col = "audit_age" if "audit_age" in df.columns else "age"
            apache_col = "audit_apache_ii" if "audit_apache_ii" in df.columns else "apache_ii"
            sex_col = "audit_sex" if "audit_sex" in df.columns else "sex"

            if age_col in df.columns:
                df["age_z"] = zscore_values(pd.to_numeric(df[age_col], errors="coerce"))
                if df["age_z"].notna().sum() >= 50:
                    covars_clinical.append("age_z")

            if apache_col in df.columns:
                df["apache_z"] = zscore_values(pd.to_numeric(df[apache_col], errors="coerce"))
                if df["apache_z"].notna().sum() >= 50:
                    covars_clinical.append("apache_z")

            if sex_col in df.columns:
                df["sex_male"] = df[sex_col].astype(str).str.lower().str.contains("male|m").astype(int)
                if df["sex_male"].nunique(dropna=True) > 1:
                    covars_clinical.append("sex_male")

            tests = {}

            for covar_name, covars in {
                "core_covars": covars_core,
                "clinical_covars": covars_clinical
            }.items():

                tests[covar_name] = {}

                tests[covar_name]["PDIA6_interaction"] = permutation_interaction(
                    df, "PDIA6_z", "PDIA6_x_vaso", covars
                )
                tests[covar_name]["PDIA6_bootstrap"] = bootstrap_interaction(
                    df, "PDIA6_z", "PDIA6_x_vaso", covars
                )
                tests[covar_name]["PDIA6_leave_one_out"] = leave_one_out(
                    df, "PDIA6_z", "PDIA6_x_vaso", covars
                )

                tests[covar_name]["PC11_interaction_reference"] = permutation_interaction(
                    df, "PC11_z", "PC11_x_vaso", covars
                )

                tests[covar_name]["combined_full_both_interactions_vs_no_interactions"] = logit_fit_lrt(
                    df,
                    "death_y",
                    ["PC11_z", "PDIA6_z", "vasopressin_bin", "PC11_x_vaso", "PDIA6_x_vaso"] + covars,
                    ["PC11_z", "PDIA6_z", "vasopressin_bin"] + covars
                )

                tests[covar_name]["does_PDIA6_add_beyond_PC11"] = logit_fit_lrt(
                    df,
                    "death_y",
                    ["PC11_z", "PDIA6_z", "vasopressin_bin", "PC11_x_vaso", "PDIA6_x_vaso"] + covars,
                    ["PC11_z", "PDIA6_z", "vasopressin_bin", "PC11_x_vaso"] + covars
                )

                tests[covar_name]["does_PC11_add_beyond_PDIA6"] = logit_fit_lrt(
                    df,
                    "death_y",
                    ["PC11_z", "PDIA6_z", "vasopressin_bin", "PC11_x_vaso", "PDIA6_x_vaso"] + covars,
                    ["PC11_z", "PDIA6_z", "vasopressin_bin", "PDIA6_x_vaso"] + covars
                )

            corr = pd.DataFrame({
                "PC11_z": df["PC11_z"],
                "PDIA6_z": df["PDIA6_z"]
            }).dropna().corr().iloc[0, 1]

            out_scores = OUT / "vanish_pdia6_validation_v8_scores.csv"
            df.to_csv(out_scores, index=False)

            result.update({
                "ok": True,
                "n_samples": int(len(df)),
                "death_col": death_col,
                "vasopressor_col": vaso_col,
                "steroid_col": steroid_col,
                "srs_col": srs_col,
                "covars_core": covars_core,
                "covars_clinical": covars_clinical,
                "pdia6_pc11_correlation": None if pd.isna(corr) else float(corr),
                "mortality_table_median_split_PDIA6": mortality_table(df, "PDIA6_z"),
                "tests": tests,
                "scores_csv": str(out_scores)
            })

json_path = OUT / "vanish_pdia6_independence_bootstrap_v8.json"
json_path.write_text(json.dumps(result, indent=2))

md = "# VANISH PDIA6 Independence + Bootstrap Validation v8\n\n"

if result.get("ok"):
    md += "## Key mapping\n\n```json\n"
    md += json.dumps({
        "pc11_merge_info": result["pc11_merge_info"],
        "pdia6_match": result["pdia6_match"],
        "pdia6_pc11_correlation": result["pdia6_pc11_correlation"],
        "covars_core": result["covars_core"],
        "covars_clinical": result["covars_clinical"]
    }, indent=2)
    md += "\n```\n\n"

    md += "## Mortality table by PDIA6 median split\n\n```text\n"
    mt = pd.DataFrame(result["mortality_table_median_split_PDIA6"])
    md += mt.to_string(index=False)
    md += "\n```\n\n"

    md += "## Core covariate tests\n\n```json\n"
    md += json.dumps(result["tests"]["core_covars"], indent=2)[:12000]
    md += "\n```\n\n"

    md += "## Clinical covariate tests\n\n```json\n"
    md += json.dumps(result["tests"]["clinical_covars"], indent=2)[:12000]
    md += "\n```\n\n"
else:
    md += "```json\n" + json.dumps(result, indent=2)[:16000] + "\n```\n\n"

md += "## Decision rule\n\n"
md += "- If PDIA6 interaction remains significant by permutation and bootstrap, PDIA6 is a strong internal candidate mechanism.\n"
md += "- If PDIA6 does not add beyond PC11, it may be a marker/component of PC11 rather than the full causal driver.\n"
md += "- If PC11 adds beyond PDIA6, PC11 remains broader than PDIA6.\n"
md += "- RUO only; not diagnostic or treatment guidance.\n"

md_path = OUT / "vanish_pdia6_independence_bootstrap_v8.md"
md_path.write_text(md)

print(json.dumps({
    "wrote_json": str(json_path),
    "wrote_markdown": str(md_path),
    "wrote_scores": str(OUT / "vanish_pdia6_validation_v8_scores.csv")
}, indent=2))
