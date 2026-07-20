from __future__ import annotations

from pathlib import Path
import json
import warnings

import anndata as ad
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from scipy.stats import chi2
from sklearn.decomposition import PCA
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


warnings.filterwarnings("ignore")

DATA = Path("data/real/vanish_steroid_safety_gate.h5ad")
OUT = Path("results/vanish_denovo_vasopressin_endotype_discovery.json")
PC_TABLE = Path("results/vanish_denovo_vasopressin_pc_scores.csv")
GROUP_TABLE = Path("results/vanish_denovo_vasopressin_candidate_groups.csv")

RANDOM_SEED = 42

N_TOP_VARIABLE_FEATURES = 5000
N_PCS = 25
N_PERMUTATIONS = 1000
N_BOOTSTRAPS = 1000


def bh_fdr(pvals):
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def make_df(a):
    obs = a.obs.copy()

    df = pd.DataFrame({
        "death": pd.to_numeric(obs["audit_death_28"], errors="coerce"),
        "srs": obs["audit_srs"].astype(str),
        "vasopressor": obs["audit_vasopressor"].astype(str),
        "steroid": obs["audit_steroid"].astype(str),
        "age": pd.to_numeric(obs["audit_age"], errors="coerce"),
        "apache": pd.to_numeric(obs["audit_apache_ii"], errors="coerce"),
        "sex": obs["audit_sex"].astype(str),
        "diabetes": pd.to_numeric(obs["audit_diabetes"], errors="coerce"),
        "immunocompromise": pd.to_numeric(obs["audit_immunocompromise"], errors="coerce"),
        "cancer": pd.to_numeric(obs["audit_cancer"], errors="coerce"),
        "copd": pd.to_numeric(obs["audit_copd"], errors="coerce"),
        "renal_failure": pd.to_numeric(obs["audit_chronic_renal_failure"], errors="coerce"),
    }, index=obs.index)

    df = df.dropna(subset=["death", "vasopressor", "steroid", "age", "apache", "sex", "srs"])
    df = df[df["vasopressor"].isin(["Noradrenaline", "Vasopressin"])]
    df = df[df["steroid"].isin(["Placebo", "Hydrocortisone"])]
    df = df[df["srs"].isin(["SRS1", "SRS2"])]

    df["vasopressor"] = pd.Categorical(df["vasopressor"], categories=["Noradrenaline", "Vasopressin"])
    df["steroid"] = pd.Categorical(df["steroid"], categories=["Placebo", "Hydrocortisone"])
    df["srs"] = pd.Categorical(df["srs"], categories=["SRS1", "SRS2"])
    df["sex"] = pd.Categorical(df["sex"])

    return df


def expression_pcs(a, df, *, n_top_variable_features=N_TOP_VARIABLE_FEATURES, n_pcs=N_PCS, random_seed=RANDOM_SEED):
    idx = [a.obs_names.get_loc(i) for i in df.index]
    X = np.asarray(a.X[idx, :], dtype=float)

    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("var", VarianceThreshold()),
        ("scaler", StandardScaler()),
    ])

    Xp = pipe.fit_transform(X)

    # Select most variable features after imputation, before PCA.
    variances = np.var(Xp, axis=0)
    k = min(n_top_variable_features, Xp.shape[1])
    top = np.argsort(variances)[-k:]
    Xtop = Xp[:, top]

    n_pcs = min(n_pcs, Xtop.shape[0] - 2, Xtop.shape[1])
    pca = PCA(n_components=n_pcs, random_state=random_seed)
    scores = pca.fit_transform(Xtop)

    pc_cols = [f"PC{i+1}" for i in range(n_pcs)]
    pcdf = pd.DataFrame(scores, index=df.index, columns=pc_cols)

    # Standardize PC scores to mean 0 / sd 1 for interpretable OR per 1 SD.
    pcdf = (pcdf - pcdf.mean(axis=0)) / pcdf.std(axis=0, ddof=0)

    explained = {
        col: float(pca.explained_variance_ratio_[i])
        for i, col in enumerate(pc_cols)
    }

    return pcdf, explained


def fit_interaction(df, pc_col):
    formula_full = f"death ~ C(vasopressor) * {pc_col} + C(steroid) + C(srs) + age + apache + C(sex)"
    formula_reduced = f"death ~ C(vasopressor) + {pc_col} + C(steroid) + C(srs) + age + apache + C(sex)"

    full = smf.logit(formula_full, data=df).fit(disp=False, maxiter=300)
    reduced = smf.logit(formula_reduced, data=df).fit(disp=False, maxiter=300)

    term = f"C(vasopressor)[T.Vasopressin]:{pc_col}"
    if term not in full.params.index:
        interaction_terms = [
            t for t in full.params.index
            if ":" in t and "vasopressor" in t.lower() and pc_col in t
        ]
        if not interaction_terms:
            raise KeyError({"available_terms": list(full.params.index), "pc": pc_col})
        term = interaction_terms[0]

    lr = 2 * (full.llf - reduced.llf)
    beta = float(full.params[term])
    ci = full.conf_int().loc[term]

    return {
        "pc": pc_col,
        "term": term,
        "beta": beta,
        "or_per_1sd": float(np.exp(beta)),
        "wald_p": float(full.pvalues[term]),
        "ci_low_or": float(np.exp(ci[0])),
        "ci_high_or": float(np.exp(ci[1])),
        "lrt": float(lr),
        "lrt_p": float(chi2.sf(lr, 1)),
        "full_llf": float(full.llf),
        "reduced_llf": float(reduced.llf),
    }


def screen_pcs(df, pcdf):
    d = pd.concat([df, pcdf], axis=1)
    rows = []
    for pc in pcdf.columns:
        try:
            rows.append(fit_interaction(d, pc))
        except Exception as e:
            rows.append({"pc": pc, "error": repr(e)})
    good = [r for r in rows if "error" not in r]
    if good:
        qvals = bh_fdr([r["lrt_p"] for r in good])
        for r, q in zip(good, qvals):
            r["lrt_fdr_bh"] = float(q)
    return rows


def permutation_for_pc(df, pcdf, pc, observed_lrt, rng, *, n_permutations=N_PERMUTATIONS):
    vals = []
    failures = 0

    base = pd.concat([df, pcdf[[pc]]], axis=1)

    for _ in range(n_permutations):
        d = base.copy()

        # Null: PC is not linked to treatment-response structure.
        # Shuffle PC within SRS × steroid strata to preserve known SRS/steroid biology.
        new_pc = []
        for _, sub in d.groupby(["srs", "steroid"], observed=False):
            arr = sub[pc].to_numpy().copy()
            rng.shuffle(arr)
            new_pc.append(pd.Series(arr, index=sub.index))
        d[pc] = pd.concat(new_pc).loc[d.index]

        try:
            res = fit_interaction(d, pc)
            vals.append(res["lrt"])
        except Exception:
            failures += 1

    vals = np.asarray(vals, dtype=float)
    return {
        "pc": pc,
        "n_permutations": int(len(vals)),
        "n_failures": int(failures),
        "null_lrt_mean": float(np.mean(vals)) if len(vals) else np.nan,
        "null_lrt_q95": float(np.quantile(vals, 0.95)) if len(vals) else np.nan,
        "null_lrt_q99": float(np.quantile(vals, 0.99)) if len(vals) else np.nan,
        "p_value_lrt_ge_observed": float((np.sum(vals >= observed_lrt) + 1) / (len(vals) + 1)) if len(vals) else np.nan,
    }


def bootstrap_for_pc(df, pcdf, pc, rng, *, n_bootstraps=N_BOOTSTRAPS):
    base = pd.concat([df, pcdf[[pc]]], axis=1)
    n = len(base)

    betas = []
    ors = []
    pvals = []
    failures = 0

    for _ in range(n_bootstraps):
        idx = rng.choice(np.arange(n), size=n, replace=True)
        d = base.iloc[idx].copy()

        if d["vasopressor"].nunique() < 2 or d["death"].nunique() < 2:
            failures += 1
            continue

        try:
            res = fit_interaction(d, pc)
            betas.append(res["beta"])
            ors.append(res["or_per_1sd"])
            pvals.append(res["wald_p"])
        except Exception:
            failures += 1

    betas = np.asarray(betas, dtype=float)
    ors = np.asarray(ors, dtype=float)
    pvals = np.asarray(pvals, dtype=float)

    return {
        "pc": pc,
        "n_bootstraps": int(len(ors)),
        "n_failures": int(failures),
        "or_median": float(np.median(ors)) if len(ors) else np.nan,
        "or_q05": float(np.quantile(ors, 0.05)) if len(ors) else np.nan,
        "or_q95": float(np.quantile(ors, 0.95)) if len(ors) else np.nan,
        "prop_beta_positive": float(np.mean(betas > 0)) if len(betas) else np.nan,
        "prop_beta_negative": float(np.mean(betas < 0)) if len(betas) else np.nan,
        "prop_p_lt_0_05": float(np.mean(pvals < 0.05)) if len(pvals) else np.nan,
    }


def metadata_r2_for_pc(df, pcdf, pc):
    d = pd.concat([df, pcdf[[pc]]], axis=1)
    formula = f"{pc} ~ age + apache + C(sex) + C(steroid) + C(srs) + diabetes + immunocompromise + cancer + copd + renal_failure"
    try:
        model = smf.ols(formula, data=d).fit()
        return {
            "pc": pc,
            "r2": float(model.rsquared),
            "adj_r2": float(model.rsquared_adj),
            "model_p": float(model.f_pvalue) if model.f_pvalue is not None else np.nan,
        }
    except Exception as e:
        return {"pc": pc, "error": repr(e)}


def candidate_group_table(df, pcdf, pc):
    d = pd.concat([df, pcdf[[pc]]], axis=1).copy()

    # Direction: high PC if beta interaction > 0 will mean vasopressin risk rises as PC rises.
    median = float(d[pc].median())
    d["candidate_endotype"] = np.where(d[pc] >= median, f"{pc}_high", f"{pc}_low")

    tab = (
        d.groupby(["candidate_endotype", "vasopressor"], observed=False)["death"]
        .agg(["count", "sum", "mean"])
        .reset_index()
    )
    return d, tab


def run_vanish_denovo_vasopressin_endotype_discovery(
    *,
    data_path=DATA,
    output_path=OUT,
    pc_table=PC_TABLE,
    group_table=GROUP_TABLE,
    n_top_variable_features=N_TOP_VARIABLE_FEATURES,
    n_pcs=N_PCS,
    n_permutations=N_PERMUTATIONS,
    n_bootstraps=N_BOOTSTRAPS,
    random_seed=RANDOM_SEED,
):
    rng = np.random.default_rng(random_seed)

    data_path = Path(data_path)
    output_path = Path(output_path)
    pc_table = Path(pc_table)
    group_table = Path(group_table)

    a = ad.read_h5ad(data_path)
    df = make_df(a)
    pcdf, explained = expression_pcs(
        a,
        df,
        n_top_variable_features=n_top_variable_features,
        n_pcs=n_pcs,
        random_seed=random_seed,
    )

    pc_scores_out = pd.concat([df, pcdf], axis=1)
    pc_table.parent.mkdir(parents=True, exist_ok=True)
    pc_scores_out.to_csv(pc_table)

    screen = screen_pcs(df, pcdf)
    valid = [r for r in screen if "error" not in r]
    valid_sorted = sorted(valid, key=lambda r: r["lrt_p"])

    top = valid_sorted[0]
    top_pc = top["pc"]

    perm = permutation_for_pc(df, pcdf, top_pc, top["lrt"], rng, n_permutations=n_permutations)
    boot = bootstrap_for_pc(df, pcdf, top_pc, rng, n_bootstraps=n_bootstraps)
    meta = metadata_r2_for_pc(df, pcdf, top_pc)

    candidate_df, candidate_tab = candidate_group_table(df, pcdf, top_pc)
    group_table.parent.mkdir(parents=True, exist_ok=True)
    candidate_df.to_csv(group_table)

    verdict = {}
    verdict["top_pc"] = top_pc

    if top.get("lrt_fdr_bh", 1.0) < 0.10 and perm["p_value_lrt_ge_observed"] < 0.05:
        verdict["discovery_signal"] = "candidate_detected"
    else:
        verdict["discovery_signal"] = "not_confirmed"

    if meta.get("r2", 1.0) < 0.25:
        verdict["metadata_explanation"] = "low_metadata_explanation_for_candidate_axis"
    else:
        verdict["metadata_explanation"] = "candidate_axis_partly_explained_by_metadata"

    if boot["prop_beta_positive"] > 0.9 or boot["prop_beta_negative"] > 0.9:
        verdict["bootstrap_direction"] = "stable_direction"
    else:
        verdict["bootstrap_direction"] = "unstable_direction"

    results = {
        "test": "VANISH de novo vasopressin response endotype discovery",
        "important_warning": "Discovery screen only; not a clinical recommendation and not proof of novelty until literature review + external validation.",
        "medical_question": "Is there a transcriptomic axis, beyond published SRS, that modifies vasopressin vs noradrenaline effect on 28-day mortality?",
        "n_patients": int(len(df)),
        "n_features": int(a.n_vars),
        "n_top_variable_features": int(n_top_variable_features),
        "n_pcs_screened": int(len(pcdf.columns)),
        "model": "death ~ vasopressor * PC + steroid + SRS + age + APACHE + sex",
        "pca_explained_variance_ratio": explained,
        "screen_results_sorted_by_lrt_p": valid_sorted,
        "top_candidate": top,
        "top_candidate_permutation": perm,
        "top_candidate_bootstrap": boot,
        "top_candidate_metadata_r2": meta,
        "top_candidate_group_mortality": candidate_tab.to_dict(orient="records"),
        "verdict": verdict,
        "outputs": {
            "pc_scores": str(pc_table),
            "candidate_groups": str(group_table),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))

    return results


def main():
    results = run_vanish_denovo_vasopressin_endotype_discovery()

    print(json.dumps(results, indent=2))
    print()
    print("Saved:", OUT)
    print("Saved:", PC_TABLE)
    print("Saved:", GROUP_TABLE)


if __name__ == "__main__":
    main()
