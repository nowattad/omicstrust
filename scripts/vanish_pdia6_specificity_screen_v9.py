from pathlib import Path
import json, re, os, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

OUT = Path("results/cross_disease_reversal_atlas")
OUT.mkdir(parents=True, exist_ok=True)

N_PERM = int(os.environ.get("V9_N_PERM", "200"))
N_BOOT = int(os.environ.get("V9_N_BOOT", "200"))
TOP_COMPETITORS = int(os.environ.get("V9_TOP_COMPETITORS", "8"))

def norm_id(x):
    return re.sub(r"[^A-Z0-9]", "", str(x).upper())

def as_array(x):
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)

def zscore(x):
    s = pd.to_numeric(pd.Series(x), errors="coerce").astype(float)
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return np.full(len(s), np.nan)
    return ((s - s.mean()) / sd).values

def corr_pair(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return np.nan
    if np.nanstd(a[ok]) == 0 or np.nanstd(b[ok]) == 0:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])

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

            corr = pd.to_numeric(r[corr_col], errors="coerce")
            if not np.isfinite(corr):
                continue

            rows.append({
                "probe_id": str(r[probe_col]).strip(),
                "symbol": sym,
                "expected_corr": float(corr),
                "loading": float(pd.to_numeric(r[loading_col], errors="coerce")) if loading_col else np.nan,
                "source_file": str(p)
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["abs_expected_corr"] = out["expected_corr"].abs()
    out["abs_loading"] = out["loading"].abs()
    out = out.drop_duplicates(subset=["probe_id", "symbol", "expected_corr"])
    return out

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
    X0 = X[ok, :]
    y = zscore(pc11[ok])

    Xmean = np.nanmean(X0, axis=0)
    Xsd = np.nanstd(X0, axis=0)
    Xsd[Xsd == 0] = np.nan

    Z = (X0 - Xmean) / Xsd
    return np.nanmean(Z * y[:, None], axis=0)

def match_annotation_to_features(ann, corrs, adata, threshold=1e-6):
    rows = []

    for _, r in ann.iterrows():
        expected = float(r["expected_corr"])
        diffs = np.abs(corrs - expected)
        idx = int(np.nanargmin(diffs))
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

    m = pd.DataFrame(rows)
    m["mapping_valid"] = m["abs_diff"] <= threshold
    return m

def bh_fdr(pvals):
    p = pd.to_numeric(pd.Series(pvals), errors="coerce").astype(float)
    out = pd.Series(np.nan, index=p.index)
    ok = p.notna() & np.isfinite(p)
    vals = p[ok].values
    if len(vals) == 0:
        return out

    order = np.argsort(vals)
    ranked = vals[order]
    q = ranked * len(vals) / (np.arange(len(vals)) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)

    idx = p[ok].index.to_numpy()[order]
    out.loc[idx] = q
    return out

def logit_lrt(df, y_col, full_cols, reduced_cols):
    try:
        import statsmodels.api as sm
        from scipy.stats import chi2
    except Exception as e:
        return {"ok": False, "error": f"missing_package:{e}"}

    cols = [y_col] + list(dict.fromkeys(full_cols + reduced_cols))
    d = df[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()

    if len(d) < 20 or d[y_col].nunique() < 2:
        return {
            "ok": False,
            "error": "insufficient_data",
            "n": int(len(d)),
            "counts": d[y_col].value_counts(dropna=False).to_dict()
        }

    y = pd.to_numeric(d[y_col], errors="coerce").astype(float)

    def Xmat(cols):
        if not cols:
            return sm.add_constant(pd.DataFrame(index=d.index), has_constant="add")
        x = d[cols].apply(pd.to_numeric, errors="coerce")
        x = x.fillna(x.median(numeric_only=True))
        return sm.add_constant(x, has_constant="add")

    try:
        full = sm.Logit(y, Xmat(full_cols)).fit(disp=False, maxiter=250)
        red = sm.Logit(y, Xmat(reduced_cols)).fit(disp=False, maxiter=250)

        df_diff = len(full_cols) - len(reduced_cols)
        lrt = float(2 * (full.llf - red.llf))
        lrt_p = float(chi2.sf(lrt, df_diff))

        return {
            "ok": True,
            "n": int(len(d)),
            "counts": d[y_col].value_counts().to_dict(),
            "lrt": lrt,
            "lrt_p": lrt_p,
            "params": {k: float(v) for k, v in full.params.to_dict().items()},
            "pvalues": {k: float(v) for k, v in full.pvalues.to_dict().items()}
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"logit_failed:{e}",
            "n": int(len(d))
        }

def fit_gene_interaction(base_df, score_col, int_col, covars):
    return logit_lrt(
        base_df,
        "death_y",
        [score_col, "vasopressin_bin", int_col] + covars,
        [score_col, "vasopressin_bin"] + covars
    )

def permutation_within_treatment(base_df, score_col, int_col, covars, n_perm=N_PERM, seed=900):
    observed = fit_gene_interaction(base_df, score_col, int_col, covars)
    if not observed.get("ok"):
        return observed

    rng = np.random.default_rng(seed)
    obs_lrt = observed["lrt"]
    ge, okn = 0, 0

    d0 = base_df.copy()
    for _ in range(n_perm):
        d = d0.copy()
        for arm in sorted(d["vasopressin_bin"].dropna().unique()):
            idx = d.index[d["vasopressin_bin"] == arm]
            d.loc[idx, score_col] = rng.permutation(d.loc[idx, score_col].values)
        d[int_col] = d[score_col] * d["vasopressin_bin"]

        fit = fit_gene_interaction(d, score_col, int_col, covars)
        if fit.get("ok"):
            ge += int(fit["lrt"] >= obs_lrt)
            okn += 1

    observed["permutation_p_within_treatment_arms"] = None if okn == 0 else float((ge + 1) / (okn + 1))
    observed["n_permutations_ok"] = int(okn)
    return observed

def bootstrap_beta(base_df, score_col, int_col, covars, n_boot=N_BOOT, seed=901):
    try:
        import statsmodels.api as sm
    except Exception as e:
        return {"ok": False, "error": f"missing_statsmodels:{e}"}

    cols = ["death_y", score_col, "vasopressin_bin", int_col] + covars
    d0 = base_df[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()

    if len(d0) < 20:
        return {"ok": False, "error": "too_few_rows", "n": int(len(d0))}

    def fit_beta(d):
        y = pd.to_numeric(d["death_y"], errors="coerce").astype(float)
        X = d[[score_col, "vasopressin_bin", int_col] + covars].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(X.median(numeric_only=True))
        X = sm.add_constant(X, has_constant="add")
        fit = sm.Logit(y, X).fit(disp=False, maxiter=200)
        return float(fit.params[int_col])

    obs = fit_gene_interaction(d0, score_col, int_col, covars)
    obs_beta = obs.get("params", {}).get(int_col)

    rng = np.random.default_rng(seed)
    betas = []

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
    return {
        "ok": True,
        "n_boot_ok": int(len(betas)),
        "observed_beta": None if obs_beta is None else float(obs_beta),
        "median_beta": float(np.median(betas)),
        "ci95_low": float(np.quantile(betas, 0.025)),
        "ci95_high": float(np.quantile(betas, 0.975)),
        "fraction_same_sign_as_observed": None if obs_beta is None else float(np.mean(np.sign(betas) == np.sign(obs_beta)))
    }

def leave_one_out(base_df, score_col, int_col, covars):
    d0 = base_df.copy()
    betas, pvals = [], []

    for i in range(len(d0)):
        d = d0.drop(d0.index[i]).copy()
        fit = fit_gene_interaction(d, score_col, int_col, covars)
        if fit.get("ok"):
            b = fit.get("params", {}).get(int_col)
            p = fit.get("pvalues", {}).get(int_col)
            if b is not None and np.isfinite(b):
                betas.append(float(b))
            if p is not None and np.isfinite(p):
                pvals.append(float(p))

    if len(betas) == 0:
        return {"ok": False, "error": "no_loo_fits"}

    betas = np.asarray(betas)
    pvals = np.asarray(pvals)

    return {
        "ok": True,
        "n_loo_ok": int(len(betas)),
        "beta_median": float(np.median(betas)),
        "beta_min": float(np.min(betas)),
        "beta_max": float(np.max(betas)),
        "fraction_beta_negative": float(np.mean(betas < 0)),
        "fraction_beta_positive": float(np.mean(betas > 0)),
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
    "test": "VANISH PDIA6 specificity screen v9",
    "question": "Is PDIA6 specific among PC11 genes, or just one of many high-PC11-loading genes?",
    "settings": {
        "n_perm_for_top_competitors": N_PERM,
        "n_boot_for_top_competitors": N_BOOT,
        "top_competitors": TOP_COMPETITORS
    },
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

        result["adata_shape"] = list(adata.shape)
        result["annotation_rows"] = int(len(ann))
        result["pc11_merge_info"] = pc11_info

        if ann.empty or pc11 is None:
            result.update({"ok": False, "error": "missing_annotation_or_pc11"})
        else:
            pc11_z = zscore(pc11)
            feature_corrs = feature_correlations_with_pc11(X, pc11)
            mapped = match_annotation_to_features(ann, feature_corrs, adata)

            valid = mapped[mapped["mapping_valid"]].copy()
            result["mapping_summary"] = {
                "n_rows": int(len(mapped)),
                "n_valid": int(len(valid)),
                "median_abs_diff": None if mapped.empty else float(mapped["abs_diff"].median()),
                "max_abs_diff": None if mapped.empty else float(mapped["abs_diff"].max())
            }

            death_col = "audit_death_28" if "audit_death_28" in obs.columns else "outcome_day_28"
            vaso_col = "audit_vasopressor" if "audit_vasopressor" in obs.columns else "drug1_per_protocol"
            steroid_col = "audit_steroid" if "audit_steroid" in obs.columns else None
            srs_col = "audit_srs" if "audit_srs" in obs.columns else "srs"

            base = obs.copy()
            base["death_y"] = binary_outcome(base[death_col])
            base["vasopressin_bin"] = base[vaso_col].astype(str).str.lower().str.contains("vasopressin").astype(int)
            base["PC11_z"] = pc11_z
            base["PC11_x_vaso"] = base["PC11_z"] * base["vasopressin_bin"]

            covars = []
            if steroid_col:
                base["steroid_bin"] = base[steroid_col].astype(str).str.lower().str.contains("hydro|steroid").astype(int)
                covars.append("steroid_bin")
            if srs_col:
                base["srs2_bin"] = base[srs_col].astype(str).str.lower().str.contains("srs2|group 2|2").astype(int)
                covars.append("srs2_bin")

            age_col = "audit_age" if "audit_age" in base.columns else "age"
            apache_col = "audit_apache_ii" if "audit_apache_ii" in base.columns else "apache_ii"

            if age_col in base.columns:
                base["age_z"] = zscore(pd.to_numeric(base[age_col], errors="coerce"))
                if pd.Series(base["age_z"]).notna().sum() >= 50:
                    covars.append("age_z")

            if apache_col in base.columns:
                base["apache_z"] = zscore(pd.to_numeric(base[apache_col], errors="coerce"))
                if pd.Series(base["apache_z"]).notna().sum() >= 50:
                    covars.append("apache_z")

            pc11_ref = fit_gene_interaction(base, "PC11_z", "PC11_x_vaso", covars)
            pc11_beta = pc11_ref.get("params", {}).get("PC11_x_vaso")

            gene_rows = []
            gene_scores = {}

            for sym, g in valid.groupby("symbol"):
                idxs = sorted(set(g["matched_feature_index0"].astype(int).tolist()))
                if not idxs:
                    continue

                expr = np.nanmedian(X[:, idxs], axis=1)
                gz = zscore(expr)

                if np.isfinite(gz).sum() < 40 or np.nanstd(gz) == 0:
                    continue

                score_col = f"gene_{sym}_z"
                int_col = f"gene_{sym}_x_vaso"

                tmp = base.copy()
                tmp[score_col] = gz
                tmp[int_col] = tmp[score_col] * tmp["vasopressin_bin"]

                fit = fit_gene_interaction(tmp, score_col, int_col, covars)
                corr_pc11 = corr_pair(gz, pc11_z)

                beta = fit.get("params", {}).get(int_col)
                p_wald = fit.get("pvalues", {}).get(int_col)
                lrt_p = fit.get("lrt_p")

                aligned_to_pc11 = None
                if beta is not None and pc11_beta is not None and np.isfinite(corr_pc11):
                    aligned_to_pc11 = bool(np.sign(beta * corr_pc11) == np.sign(pc11_beta))

                gene_rows.append({
                    "symbol": sym,
                    "n_probes": int(len(idxs)),
                    "corr_to_PC11": None if not np.isfinite(corr_pc11) else float(corr_pc11),
                    "abs_corr_to_PC11": None if not np.isfinite(corr_pc11) else float(abs(corr_pc11)),
                    "mean_expected_corr": float(g["expected_corr"].mean()),
                    "max_abs_expected_corr": float(g["expected_corr"].abs().max()),
                    "interaction_beta": None if beta is None else float(beta),
                    "interaction_wald_p": None if p_wald is None else float(p_wald),
                    "interaction_lrt": fit.get("lrt"),
                    "interaction_lrt_p": None if lrt_p is None else float(lrt_p),
                    "aligned_to_PC11": aligned_to_pc11,
                    "model_ok": bool(fit.get("ok")),
                    "model_error": fit.get("error")
                })

                gene_scores[sym] = gz

            screen = pd.DataFrame(gene_rows)

            if not screen.empty:
                screen["interaction_lrt_fdr"] = bh_fdr(screen["interaction_lrt_p"]).values
                screen["interaction_wald_fdr"] = bh_fdr(screen["interaction_wald_p"]).values

                screen = screen.sort_values(
                    by=["model_ok", "aligned_to_PC11", "interaction_lrt_p"],
                    ascending=[False, False, True],
                    na_position="last"
                )

            screen_csv = OUT / "vanish_pdia6_specificity_screen_v9_all_genes.csv"
            screen.to_csv(screen_csv, index=False)

            pdia6_info = {}
            matched_null = {}

            if not screen.empty and (screen["symbol"] == "PDIA6").any():
                pdia6_row = screen[screen["symbol"] == "PDIA6"].iloc[0].to_dict()
                pdia6_info = pdia6_row

                pdia6_abs_corr = pdia6_row.get("abs_corr_to_PC11")
                pdia6_p = pdia6_row.get("interaction_lrt_p")

                pool = screen[
                    (screen["model_ok"] == True) &
                    (screen["symbol"] != "PDIA6") &
                    (screen["abs_corr_to_PC11"].notna()) &
                    (screen["interaction_lrt_p"].notna())
                ].copy()

                if pdia6_abs_corr is not None and np.isfinite(pdia6_abs_corr):
                    matched = pool[(pool["abs_corr_to_PC11"] - pdia6_abs_corr).abs() <= 0.05].copy()

                    if len(matched) < 20:
                        pool["distance_to_PDIA6_abs_corr"] = (pool["abs_corr_to_PC11"] - pdia6_abs_corr).abs()
                        matched = pool.sort_values("distance_to_PDIA6_abs_corr").head(50).copy()

                    n = len(matched)
                    if n > 0 and pdia6_p is not None and np.isfinite(pdia6_p):
                        matched_null = {
                            "mode": "abs_corr_matched_null",
                            "pdia6_abs_corr_to_PC11": float(pdia6_abs_corr),
                            "pdia6_lrt_p": float(pdia6_p),
                            "n_matched_genes": int(n),
                            "n_matched_with_lrt_p_le_pdia6": int((matched["interaction_lrt_p"] <= pdia6_p).sum()),
                            "empirical_p_rank": float(((matched["interaction_lrt_p"] <= pdia6_p).sum() + 1) / (n + 1)),
                            "pdia6_rank_among_matched_plus_self_by_lrt_p": int(1 + (matched["interaction_lrt_p"] < pdia6_p).sum()),
                            "matched_gene_symbols_p_le_pdia6": matched.loc[
                                matched["interaction_lrt_p"] <= pdia6_p,
                                "symbol"
                            ].head(30).tolist(),
                            "matched_top10_by_lrt_p": matched.sort_values("interaction_lrt_p").head(10).to_dict(orient="records")
                        }

                    matched.to_csv(OUT / "vanish_pdia6_specificity_screen_v9_matched_null.csv", index=False)

            # Robustness only for PDIA6 + top aligned competitors.
            robust_details = {}
            robust_rows = []

            if not screen.empty:
                eligible = screen[
                    (screen["model_ok"] == True) &
                    (screen["interaction_lrt_p"].notna()) &
                    (screen["aligned_to_PC11"] == True)
                ].copy()

                top_syms = []
                if "PDIA6" in gene_scores:
                    top_syms.append("PDIA6")

                for s in eligible["symbol"].tolist():
                    if s not in top_syms:
                        top_syms.append(s)
                    if len(top_syms) >= TOP_COMPETITORS + 1:
                        break

                for sym in top_syms:
                    if sym not in gene_scores:
                        continue

                    score_col = f"gene_{sym}_z"
                    int_col = f"gene_{sym}_x_vaso"

                    tmp = base.copy()
                    tmp[score_col] = gene_scores[sym]
                    tmp[int_col] = tmp[score_col] * tmp["vasopressin_bin"]

                    interaction = permutation_within_treatment(tmp, score_col, int_col, covars)
                    boot = bootstrap_beta(tmp, score_col, int_col, covars)
                    loo = leave_one_out(tmp, score_col, int_col, covars)
                    mt = mortality_table(tmp, score_col)

                    robust_details[sym] = {
                        "interaction": interaction,
                        "bootstrap": boot,
                        "leave_one_out": loo,
                        "mortality_table": mt
                    }

                    robust_rows.append({
                        "symbol": sym,
                        "lrt_p": interaction.get("lrt_p"),
                        "permutation_p": interaction.get("permutation_p_within_treatment_arms"),
                        "beta": interaction.get("params", {}).get(int_col),
                        "wald_p": interaction.get("pvalues", {}).get(int_col),
                        "bootstrap_fraction_same_sign": boot.get("fraction_same_sign_as_observed"),
                        "bootstrap_ci95_low": boot.get("ci95_low"),
                        "bootstrap_ci95_high": boot.get("ci95_high"),
                        "loo_fraction_p_lt_0_05": loo.get("fraction_p_lt_0_05"),
                        "loo_fraction_beta_negative": loo.get("fraction_beta_negative"),
                        "loo_fraction_beta_positive": loo.get("fraction_beta_positive")
                    })

            robust = pd.DataFrame(robust_rows)
            robust_csv = OUT / "vanish_pdia6_specificity_screen_v9_top_robustness.csv"
            robust.to_csv(robust_csv, index=False)

            result.update({
                "ok": True,
                "death_col": death_col,
                "vasopressor_col": vaso_col,
                "steroid_col": steroid_col,
                "srs_col": srs_col,
                "covariates": covars,
                "pc11_reference_model": pc11_ref,
                "pc11_interaction_beta": pc11_beta,
                "n_genes_screened": int(len(screen)),
                "pdia6_info": pdia6_info,
                "matched_null": matched_null,
                "top20_screen": screen.head(20).to_dict(orient="records") if not screen.empty else [],
                "robustness_top_competitors": robust_details,
                "all_gene_screen_csv": str(screen_csv),
                "robustness_csv": str(robust_csv)
            })

json_path = OUT / "vanish_pdia6_specificity_screen_v9.json"
json_path.write_text(json.dumps(result, indent=2, default=str))

md = "# VANISH PDIA6 Specificity Screen v9\n\n"
md += "Question: is PDIA6 specific among PC11 genes, or just one of many high-PC11-loading genes?\n\n"

if result.get("ok"):
    md += "## Settings\n\n```json\n"
    md += json.dumps(result["settings"], indent=2)
    md += "\n```\n\n"

    md += "## Mapping summary\n\n```json\n"
    md += json.dumps(result.get("mapping_summary", {}), indent=2)
    md += "\n```\n\n"

    md += "## PC11 reference\n\n```json\n"
    md += json.dumps(result.get("pc11_reference_model", {}), indent=2)[:5000]
    md += "\n```\n\n"

    md += "## PDIA6 row\n\n```json\n"
    md += json.dumps(result.get("pdia6_info", {}), indent=2)
    md += "\n```\n\n"

    md += "## Matched-null comparison\n\n```json\n"
    md += json.dumps(result.get("matched_null", {}), indent=2)[:8000]
    md += "\n```\n\n"

    md += "## Top 20 all-PC11 single-gene screen\n\n```text\n"
    top = pd.DataFrame(result.get("top20_screen", []))
    if not top.empty:
        keep = [
            "symbol", "n_probes", "corr_to_PC11", "interaction_beta",
            "interaction_lrt_p", "interaction_lrt_fdr",
            "interaction_wald_p", "aligned_to_PC11"
        ]
        keep = [c for c in keep if c in top.columns]
        md += top[keep].to_string(index=False)
    else:
        md += "No top rows."
    md += "\n```\n\n"

    md += "## Robustness: PDIA6 + top aligned competitors\n\n```text\n"
    rob = pd.read_csv(result["robustness_csv"]) if Path(result["robustness_csv"]).exists() else pd.DataFrame()
    if not rob.empty:
        md += rob.to_string(index=False)
    else:
        md += "No robustness rows."
    md += "\n```\n\n"

    md += "## Top robustness details\n\n```json\n"
    md += json.dumps(result.get("robustness_top_competitors", {}), indent=2, default=str)[:14000]
    md += "\n```\n\n"

else:
    md += "```json\n" + json.dumps(result, indent=2, default=str)[:16000] + "\n```\n\n"

md += "## Decision rule\n\n"
md += "- If PDIA6 ranks near the top, is directionally aligned with PC11, and remains robust compared with matched high-PC11 genes, it is a strong mechanistic anchor.\n"
md += "- If many matched genes equal or outperform PDIA6, interpret PDIA6 as part of a broader submodule rather than a unique anchor.\n"
md += "- If PDIA6 is not near the top or loses robustness, downgrade it to marker/component only.\n"
md += "- RUO only; not diagnostic or treatment guidance.\n"

md_path = OUT / "vanish_pdia6_specificity_screen_v9.md"
md_path.write_text(md)

print(json.dumps({
    "wrote_json": str(json_path),
    "wrote_markdown": str(md_path),
    "wrote_all_gene_screen": result.get("all_gene_screen_csv"),
    "wrote_robustness": result.get("robustness_csv")
}, indent=2))
