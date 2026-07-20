from pathlib import Path
import json, re, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

OUT = Path("results/cross_disease_reversal_atlas")
OUT.mkdir(parents=True, exist_ok=True)

GENESETS = {
    "interferon_antiviral_failed_control": [
        "ISG15","IFIT1","IFIT2","IFIT3","IFI6","IFI27","IFI44","IFI44L",
        "MX1","MX2","OAS1","OAS2","OAS3","OASL","RSAD2","IRF7","IRF9",
        "STAT1","STAT2","DDX58","GBP1","GBP2","CXCL10","XAF1","HERC5","HERC6"
    ],
    "myeloid_inhibitory_lilr_axis": [
        "LILRB1","LILRB2","LILRB3","LILRB4","LILRA1","LILRA2","LILRA3","LILRA5",
        "LAIR1","SIGLEC5","SIGLEC9","FCGR2A","FCGR2B","FCGR3A","TYROBP",
        "LST1","AIF1","MS4A7","CTSS","LYZ"
    ],
    "er_stress_protein_folding_axis": [
        "PDIA6","P4HB","HSPA5","HSP90B1","CANX","CALR","ERP44","DNAJB9",
        "HERPUD1","SELENOS","SEC61A1","DERL1","EDEM1","XBP1","ATF4","DDIT3"
    ],
    "lilr_core": ["LILRB1","LILRB4"],
    "pdia6_core": ["PDIA6"]
}

def norm_id(x):
    return re.sub(r"[^A-Z0-9]", "", str(x).upper())

def as_array(x):
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)

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
    if num.notna().sum() >= 10 and set(num.dropna().unique()).issubset({0,1}):
        return num

    y = pd.Series(np.nan, index=s.index)
    y[vals.str.contains("death|dead|died|non-survivor|non survivor|yes|true", regex=True)] = 1
    y[vals.str.contains("alive|survivor|survived|no|false", regex=True)] = 0
    return y

def read_pc11_annotations():
    files = {
        "positive": Path("results/vanish_pc11_positive_illumina_annotated.csv"),
        "negative": Path("results/vanish_pc11_negative_illumina_annotated.csv"),
        "top": Path("results/vanish_pc11_top_probe_loadings_illumina_annotated.csv"),
    }

    rows = []
    for side, p in files.items():
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
                "side": side,
                "expected_corr": float(pd.to_numeric(r[corr_col], errors="coerce")),
                "loading": float(pd.to_numeric(r[loading_col], errors="coerce")) if loading_col else np.nan,
                "abs_loading": abs(float(pd.to_numeric(r[loading_col], errors="coerce"))) if loading_col else np.nan,
                "source_file": str(p)
            })

    all_df = pd.DataFrame(rows)
    if all_df.empty:
        return all_df

    all_df = all_df.dropna(subset=["probe_id", "symbol", "expected_corr"])
    all_df = all_df.drop_duplicates(subset=["probe_id", "symbol", "side"])
    return all_df

def load_pc11_for_adata(obs):
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
    obs_df["__obs_index__"] = obs_df.index.astype(str)

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
        a = obs_df[[oc]].copy()
        a["_id"] = a[oc].astype(str).map(norm_id)
        b = pc[[pc_col, pc11_col]].copy()
        b["_id"] = b[pc_col].astype(str).map(norm_id)
        merged = a.merge(b[["_id", pc11_col]], on="_id", how="left")
        pc11 = pd.to_numeric(merged[pc11_col], errors="coerce").values
        return pc11, {
            "ok": True,
            "mode": "id_merge",
            "obs_col": oc,
            "pc_col": pc_col,
            "n_overlap": int(best_n),
            "pc11_col": pc11_col,
            "pc_path": str(pc_path)
        }

    if len(pc) == len(obs_df):
        pc11 = pd.to_numeric(pc[pc11_col], errors="coerce").values
        return pc11, {
            "ok": True,
            "mode": "row_order_equal_length",
            "pc11_col": pc11_col,
            "pc_path": str(pc_path)
        }

    return None, {
        "ok": False,
        "error": "could_not_merge_pc11_to_adata_obs",
        "pc_shape": list(pc.shape),
        "obs_shape": list(obs_df.shape),
        "pc_columns": pc.columns.tolist(),
        "obs_columns": obs_df.columns.tolist()
    }

def feature_correlations_with_pc11(X, pc11):
    pc11 = np.asarray(pc11, dtype=float)
    ok = np.isfinite(pc11)
    X = X[ok, :]
    y = pc11[ok]

    y = y - np.nanmean(y)
    ysd = np.nanstd(y)
    y = y / ysd

    Xmean = np.nanmean(X, axis=0)
    Xsd = np.nanstd(X, axis=0)
    Xsd[Xsd == 0] = np.nan
    Z = (X - Xmean) / Xsd
    return np.nanmean(Z * y[:, None], axis=0)

def fingerprint_match_targets(targets, corrs, adata, max_abs_diff=1e-3):
    matches = []
    used = set()

    for _, r in targets.iterrows():
        expected = float(r["expected_corr"])
        diffs = np.abs(corrs - expected)
        order = np.argsort(diffs)

        best_idx = None
        for idx in order[:100]:
            if int(idx) not in used:
                best_idx = int(idx)
                break
        if best_idx is None:
            best_idx = int(order[0])

        used.add(best_idx)

        matches.append({
            "probe_id": r["probe_id"],
            "symbol": r["symbol"],
            "side": r["side"],
            "expected_corr": expected,
            "matched_feature_index0": best_idx,
            "matched_feature_name": str(adata.var_names[best_idx]),
            "observed_corr": float(corrs[best_idx]),
            "abs_diff": float(abs(corrs[best_idx] - expected)),
            "loading": None if pd.isna(r.get("loading", np.nan)) else float(r["loading"])
        })

    m = pd.DataFrame(matches)
    if m.empty:
        return m, {"ok": False, "error": "empty_match"}

    valid = m["abs_diff"] <= max_abs_diff
    quality = {
        "ok": bool(valid.sum() >= max(1, int(0.70 * len(m)))),
        "n_targets": int(len(m)),
        "n_valid": int(valid.sum()),
        "median_abs_diff": float(m["abs_diff"].median()),
        "max_abs_diff": float(m["abs_diff"].max())
    }
    return m, quality

def build_module_score(X, obs_index, matched):
    valid = matched[matched["abs_diff"] <= 1e-3].copy()
    if valid.empty:
        return None, {"ok": False, "error": "no_valid_features"}

    gene_expr = pd.DataFrame(index=obs_index.astype(str))
    for gene in sorted(valid["symbol"].unique()):
        idxs = valid.loc[valid["symbol"] == gene, "matched_feature_index0"].astype(int).tolist()
        vals = X[:, idxs]
        gene_expr[gene] = np.nanmedian(vals, axis=1)

    if gene_expr.shape[1] == 0:
        return None, {"ok": False, "error": "no_gene_expr"}

    z = (gene_expr - gene_expr.mean(axis=0)) / gene_expr.std(axis=0, ddof=0).replace(0, np.nan)
    score = z.mean(axis=1)

    return score, {
        "ok": True,
        "n_genes": int(gene_expr.shape[1]),
        "genes": list(gene_expr.columns),
        "n_features": int(len(valid))
    }

def logit_lrt(df, y_col, full_cols, reduced_cols, n_perm=300, seed=31):
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
        obs_lrt = float(2 * (full.llf - red.llf))
        p = float(chi2.sf(obs_lrt, len(full_cols) - len(reduced_cols)))
    except Exception as e:
        return {"ok": False, "error": f"logit_failed:{e}", "n": int(len(d))}

    perm_p = None
    interaction_cols = [c for c in full_cols if c.endswith("_x_vaso")]
    if interaction_cols:
        int_col = interaction_cols[0]
        rng = np.random.default_rng(seed)
        ge, okn = 0, 0
        d0 = d.copy()
        for _ in range(n_perm):
            d[int_col] = rng.permutation(d0[int_col].values)
            try:
                fp = sm.Logit(y, Xmat(full_cols)).fit(disp=False, maxiter=150)
                rp = sm.Logit(y, Xmat(reduced_cols)).fit(disp=False, maxiter=150)
                lrtp = float(2 * (fp.llf - rp.llf))
                ge += int(lrtp >= obs_lrt)
                okn += 1
            except Exception:
                pass
        if okn:
            perm_p = float((ge + 1) / (okn + 1))

    return {
        "ok": True,
        "n": int(len(d)),
        "counts": d[y_col].value_counts().to_dict(),
        "lrt": obs_lrt,
        "lrt_p": p,
        "permutation_p": perm_p,
        "params": {k: float(v) for k, v in full.params.to_dict().items()},
        "pvalues": {k: float(v) for k, v in full.pvalues.to_dict().items()}
    }

def zscore(s):
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return (s - s.mean()) / s.std(ddof=0)

result = {
    "test": "VANISH PC11 mechanism screen v7",
    "goal": "Find which PC11-derived biological sub-axis best reproduces PC11 × vasopressin mortality interaction.",
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
        obs = adata.obs.copy()
        obs["sample_id"] = obs.index.astype(str)

        pc11, pc_info = load_pc11_for_adata(obs)
        ann = read_pc11_annotations()

        result["adata_shape"] = list(adata.shape)
        result["pc11_merge_info"] = pc_info
        result["annotation_rows"] = int(len(ann))

        if pc11 is None or ann.empty:
            result.update({"ok": False, "error": "missing_pc11_or_annotations"})
        else:
            X = as_array(adata.X)
            corrs = feature_correlations_with_pc11(X, pc11)

            death_col = "audit_death_28" if "audit_death_28" in obs.columns else "outcome_day_28"
            vaso_col = "audit_vasopressor" if "audit_vasopressor" in obs.columns else "drug1_per_protocol"
            steroid_col = "audit_steroid" if "audit_steroid" in obs.columns else None
            srs_col = "audit_srs" if "audit_srs" in obs.columns else "srs"

            model_df = obs.copy()
            model_df["death_y"] = binary_outcome(model_df[death_col])
            model_df["vasopressin_bin"] = model_df[vaso_col].astype(str).str.lower().str.contains("vasopressin").astype(int)
            model_df["PC11_z"] = zscore(pc11)
            model_df["PC11_x_vaso"] = model_df["PC11_z"] * model_df["vasopressin_bin"]

            covars = []
            if steroid_col:
                model_df["steroid_bin"] = model_df[steroid_col].astype(str).str.lower().str.contains("hydro|steroid").astype(int)
                covars.append("steroid_bin")
            if srs_col:
                model_df["srs2_bin"] = model_df[srs_col].astype(str).str.lower().str.contains("srs2|group 2|2").astype(int)
                covars.append("srs2_bin")

            pc11_reference = logit_lrt(
                model_df,
                "death_y",
                ["PC11_z", "vasopressin_bin", "PC11_x_vaso"] + covars,
                ["PC11_z", "vasopressin_bin"] + covars
            )

            candidate_defs = {}

            pos = ann[ann["side"] == "positive"].sort_values("abs_loading", ascending=False)
            neg = ann[ann["side"] == "negative"].sort_values("abs_loading", ascending=False)

            candidate_defs["pc11_positive_top25"] = pos.head(25)
            candidate_defs["pc11_negative_top25"] = neg.head(25)
            candidate_defs["pc11_positive_top50"] = pos.head(50)
            candidate_defs["pc11_negative_top50"] = neg.head(50)

            for name, genes in GENESETS.items():
                genes = set([g.upper() for g in genes])
                candidate_defs[name] = ann[ann["symbol"].isin(genes)]

            module_results = {}
            score_table = model_df[["sample_id","death_y","vasopressin_bin"] + covars + ["PC11_z"]].copy()

            for name, targets in candidate_defs.items():
                targets = targets.drop_duplicates(subset=["probe_id", "symbol"])
                if targets.empty:
                    module_results[name] = {"ok": False, "error": "no_matching_pc11_annotated_targets"}
                    continue

                matched, quality = fingerprint_match_targets(targets, corrs, adata)
                score, score_info = build_module_score(X, obs.index, matched)

                module_results[name] = {
                    "n_targets": int(len(targets)),
                    "mapping_quality": quality,
                    "score_info": score_info,
                    "target_genes": sorted(targets["symbol"].dropna().unique().tolist())
                }

                if score is None or not quality.get("ok"):
                    module_results[name]["ok"] = False
                    module_results[name]["error"] = "mapping_or_score_failed"
                    continue

                col = f"{name}_z"
                int_col = f"{name}_x_vaso"

                model_df[col] = zscore(score.values).values
                model_df[int_col] = model_df[col] * model_df["vasopressin_bin"]

                corr_pc11 = pd.DataFrame({
                    "module": model_df[col],
                    "PC11": model_df["PC11_z"]
                }).dropna().corr().iloc[0,1]

                model = logit_lrt(
                    model_df,
                    "death_y",
                    [col, "vasopressin_bin", int_col] + covars,
                    [col, "vasopressin_bin"] + covars
                )

                module_results[name].update({
                    "ok": True,
                    "module_pc11_correlation": None if pd.isna(corr_pc11) else float(corr_pc11),
                    "interaction_model": model
                })

                score_table[col] = model_df[col]

            # Reconstruction: positive minus negative
            if "pc11_positive_top50_z" in model_df.columns and "pc11_negative_top50_z" in model_df.columns:
                model_df["pc11_reconstruction_pos_minus_neg_z"] = zscore(
                    model_df["pc11_positive_top50_z"] - model_df["pc11_negative_top50_z"]
                )
                model_df["pc11_reconstruction_pos_minus_neg_x_vaso"] = (
                    model_df["pc11_reconstruction_pos_minus_neg_z"] * model_df["vasopressin_bin"]
                )

                corr_rec = pd.DataFrame({
                    "reconstruction": model_df["pc11_reconstruction_pos_minus_neg_z"],
                    "PC11": model_df["PC11_z"]
                }).dropna().corr().iloc[0,1]

                rec_model = logit_lrt(
                    model_df,
                    "death_y",
                    ["pc11_reconstruction_pos_minus_neg_z", "vasopressin_bin", "pc11_reconstruction_pos_minus_neg_x_vaso"] + covars,
                    ["pc11_reconstruction_pos_minus_neg_z", "vasopressin_bin"] + covars
                )

                module_results["pc11_reconstruction_pos_minus_neg_top50"] = {
                    "ok": True,
                    "module_pc11_correlation": float(corr_rec),
                    "interaction_model": rec_model,
                    "note": "Top positive 50 minus top negative 50 reconstruction."
                }

            summary_rows = []
            for name, r in module_results.items():
                model = r.get("interaction_model", {})
                summary_rows.append({
                    "module": name,
                    "ok": r.get("ok", False),
                    "n_targets": r.get("n_targets"),
                    "n_genes": r.get("score_info", {}).get("n_genes"),
                    "module_pc11_correlation": r.get("module_pc11_correlation"),
                    "interaction_lrt_p": model.get("lrt_p"),
                    "interaction_perm_p": model.get("permutation_p"),
                    "interaction_beta": model.get("params", {}).get(f"{name}_x_vaso"),
                    "target_genes": ",".join(r.get("target_genes", [])[:30]) if isinstance(r.get("target_genes"), list) else None
                })

            summary = pd.DataFrame(summary_rows)
            if not summary.empty:
                summary = summary.sort_values(
                    by=["ok", "interaction_lrt_p"],
                    ascending=[False, True],
                    na_position="last"
                )

            scores_path = OUT / "vanish_pc11_mechanism_screen_v7_scores.csv"
            summary_path = OUT / "vanish_pc11_mechanism_screen_v7_summary.csv"
            model_df.to_csv(scores_path, index=False)
            summary.to_csv(summary_path, index=False)

            result.update({
                "ok": True,
                "death_col": death_col,
                "vasopressor_col": vaso_col,
                "steroid_col": steroid_col,
                "srs_col": srs_col,
                "pc11_reference_model": pc11_reference,
                "module_results": module_results,
                "summary_table": summary.to_dict(orient="records"),
                "scores_csv": str(scores_path),
                "summary_csv": str(summary_path)
            })

json_path = OUT / "vanish_pc11_mechanism_screen_v7.json"
json_path.write_text(json.dumps(result, indent=2))

md = "# VANISH PC11 Mechanism Screen v7\n\n"
md += "Goal: find which PC11-derived biological sub-axis best reproduces PC11 × vasopressin mortality interaction.\n\n"

if result.get("ok"):
    md += "## PC11 reference model\n\n```json\n"
    md += json.dumps(result.get("pc11_reference_model", {}), indent=2)
    md += "\n```\n\n"

    md += "## Summary table\n\n"
    summary = pd.DataFrame(result.get("summary_table", []))
    if not summary.empty:
        md += summary.to_markdown(index=False)
    else:
        md += "No summary rows."
    md += "\n\n"

    md += "## Top module details\n\n```json\n"
    top_names = [r["module"] for r in result.get("summary_table", [])[:5]]
    top_details = {k: result["module_results"][k] for k in top_names if k in result["module_results"]}
    md += json.dumps(top_details, indent=2)[:14000]
    md += "\n```\n\n"
else:
    md += "```json\n" + json.dumps(result, indent=2)[:16000] + "\n```\n\n"

md += "## Decision rule\n\n"
md += "- A plausible PC11 mechanism should map cleanly, correlate with PC11, and show a treatment interaction directionally similar to PC11.\n"
md += "- If no sub-axis reproduces the interaction, PC11 remains an internal response axis but mechanism remains unresolved.\n"
md += "- RUO only; not diagnostic or treatment guidance.\n"

md_path = OUT / "vanish_pc11_mechanism_screen_v7.md"
md_path.write_text(md)

print(json.dumps({
    "wrote_json": str(json_path),
    "wrote_markdown": str(md_path),
    "wrote_summary_csv": str(OUT / "vanish_pc11_mechanism_screen_v7_summary.csv")
}, indent=2))
