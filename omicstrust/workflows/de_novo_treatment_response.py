from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2
from sklearn.decomposition import PCA
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


RANDOM_SEED = 42

VANISH_DEFAULT_MAPPING = {
    "treatment_key": "audit_vasopressor",
    "outcome_key": "audit_death_28",
    "steroid_key": "audit_steroid",
    "srs_key": "audit_srs",
    "age_key": "audit_age",
    "sex_key": "audit_sex",
    "apache_key": "audit_apache_ii",
    "patient_key": "individual",
    "covariate_keys": ["audit_steroid", "audit_srs", "audit_age", "audit_apache_ii", "audit_sex"],
}


def vanish_default_mapping() -> dict[str, Any]:
    return dict(VANISH_DEFAULT_MAPPING)


def run_de_novo_treatment_response_discovery(
    *,
    data_path: str | Path,
    output_dir: str | Path,
    treatment_key: str | None = None,
    outcome_key: str | None = None,
    covariate_keys: list[str] | None = None,
    patient_id_key: str | None = None,
    batch_key: str | None = None,
    known_endotype_key: str | None = None,
    dataset_adapter: str | None = None,
    n_top_variable_features: int = 5000,
    n_axes: int | None = None,
    n_pcs: int | None = None,
    model_family: str = "logistic",
    permutation_n: int = 1000,
    bootstrap_n: int = 1000,
    random_seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Run a controlled RUO de novo treatment-response discovery workflow.

    The executor is generic: it accepts a local omics matrix plus treatment and
    outcome columns. Dataset-specific adapters may fill those mappings, but they
    do not own the Copilot routing contract.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = Path(data_path)
    covariate_keys = list(covariate_keys or [])
    n_components = int(n_axes or n_pcs or 25)

    if _normalize_adapter(dataset_adapter) == "vanish_default_mapping":
        return _run_vanish_adapter(
            data_path=data_path,
            output_dir=output_dir,
            n_top_variable_features=n_top_variable_features,
            n_pcs=n_components,
            permutation_n=permutation_n,
            bootstrap_n=bootstrap_n,
            random_seed=random_seed,
        )

    missing = []
    if not treatment_key:
        missing.append("treatment_key")
    if not outcome_key:
        missing.append("outcome_key")
    if missing:
        return {
            "status": "missing_inputs",
            "missing": missing,
            "message": "Generic discovery requires treatment_key and outcome_key unless a dataset adapter supplies them.",
            "dataset_adapter": dataset_adapter,
        }
    if model_family != "logistic":
        return {
            "status": "unsupported_workflow",
            "reason": "unsupported_model_family",
            "message": "Only logistic treatment-response discovery is currently enabled.",
            "model_family": model_family,
        }

    return _run_generic_discovery(
        data_path=data_path,
        output_dir=output_dir,
        treatment_key=treatment_key,
        outcome_key=outcome_key,
        covariate_keys=covariate_keys,
        patient_id_key=patient_id_key,
        batch_key=batch_key,
        known_endotype_key=known_endotype_key,
        n_top_variable_features=n_top_variable_features,
        n_pcs=n_components,
        permutation_n=permutation_n,
        bootstrap_n=bootstrap_n,
        random_seed=random_seed,
    )


def _run_vanish_adapter(
    *,
    data_path: Path,
    output_dir: Path,
    n_top_variable_features: int,
    n_pcs: int,
    permutation_n: int,
    bootstrap_n: int,
    random_seed: int,
) -> dict[str, Any]:
    run_vanish_denovo_vasopressin_endotype_discovery = _load_vanish_runner()

    result = run_vanish_denovo_vasopressin_endotype_discovery(
        data_path=data_path,
        output_path=output_dir / "vanish_denovo_vasopressin_endotype_discovery.json",
        pc_table=output_dir / "vanish_denovo_vasopressin_pc_scores.csv",
        group_table=output_dir / "vanish_denovo_vasopressin_candidate_groups.csv",
        n_top_variable_features=n_top_variable_features,
        n_pcs=n_pcs,
        n_permutations=permutation_n,
        n_bootstraps=bootstrap_n,
        random_seed=random_seed,
    )
    result["status"] = "completed"
    result["dataset_adapter"] = "vanish_default_mapping"
    result["mapping"] = vanish_default_mapping()
    result["ruo_claim_boundary"] = _ruo_claim_boundary()
    return result


def _load_vanish_runner():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "vanish_denovo_vasopressin_endotype_discovery.py"
    spec = importlib.util.spec_from_file_location("omicstrust_vanish_denovo_discovery_script", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load VANISH discovery script from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_vanish_denovo_vasopressin_endotype_discovery


def _run_generic_discovery(
    *,
    data_path: Path,
    output_dir: Path,
    treatment_key: str,
    outcome_key: str,
    covariate_keys: list[str],
    patient_id_key: str | None,
    batch_key: str | None,
    known_endotype_key: str | None,
    n_top_variable_features: int,
    n_pcs: int,
    permutation_n: int,
    bootstrap_n: int,
    random_seed: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(random_seed)
    metadata_keys = [treatment_key, outcome_key, patient_id_key, batch_key, known_endotype_key] + covariate_keys
    obs, X, feature_count = _load_matrix_and_obs(data_path, metadata_keys=metadata_keys)
    df = _generic_design_frame(obs, treatment_key, outcome_key, covariate_keys, patient_id_key, batch_key, known_endotype_key)
    X = X[[obs.index.get_loc(idx) for idx in df.index], :]
    pcdf, explained = _expression_pcs(
        X,
        df.index,
        n_top_variable_features=n_top_variable_features,
        n_pcs=n_pcs,
        random_seed=random_seed,
    )
    screen = _screen_generic_pcs(df, pcdf, covariate_keys)
    valid = [row for row in screen if "error" not in row]
    if not valid:
        return {"status": "failed", "reason": "no_valid_pc_models", "screen_results": screen}

    valid_sorted = sorted(valid, key=lambda row: row["lrt_p"])
    top = valid_sorted[0]
    top_pc = top["pc"]
    perm = _generic_permutation(df, pcdf, top_pc, top["lrt"], covariate_keys, rng, permutation_n)
    boot = _generic_bootstrap(df, pcdf, top_pc, covariate_keys, rng, bootstrap_n)
    meta = _generic_metadata_r2(df, pcdf, top_pc, covariate_keys, batch_key, known_endotype_key)
    scored_df, group_table = _generic_group_table(df, pcdf, top_pc)

    pc_table = output_dir / "de_novo_pc_scores.csv"
    group_path = output_dir / "de_novo_candidate_groups.csv"
    json_path = output_dir / "de_novo_treatment_response_discovery.json"
    pd.concat([df, pcdf], axis=1).to_csv(pc_table)
    scored_df.to_csv(group_path)

    verdict = {
        "top_pc": top_pc,
        "discovery_signal": "candidate_detected"
        if top.get("lrt_fdr_bh", 1.0) < 0.10 and perm.get("p_value_lrt_ge_observed", 1.0) < 0.05
        else "not_confirmed",
        "metadata_explanation": "low_metadata_explanation_for_candidate_axis"
        if meta.get("r2", 1.0) < 0.25
        else "candidate_axis_partly_explained_by_metadata",
        "bootstrap_direction": "stable_direction"
        if boot.get("prop_beta_positive", 0.0) > 0.9 or boot.get("prop_beta_negative", 0.0) > 0.9
        else "unstable_direction",
    }
    result = {
        "status": "completed",
        "test": "Generic de novo treatment response discovery",
        "important_warning": "Discovery screen only; not a clinical recommendation and not proof of biological or clinical validity.",
        "n_patients": int(len(df)),
        "n_features": int(feature_count),
        "n_top_variable_features": int(n_top_variable_features),
        "n_pcs_screened": int(len(pcdf.columns)),
        "mapping": {
            "treatment_key": treatment_key,
            "outcome_key": outcome_key,
            "patient_id_key": patient_id_key,
            "covariate_keys": covariate_keys,
            "batch_key": batch_key,
            "known_endotype_key": known_endotype_key,
        },
        "model": "outcome ~ treatment * PC + covariates",
        "pca_explained_variance_ratio": explained,
        "screen_results_sorted_by_lrt_p": valid_sorted,
        "top_candidate": top,
        "top_candidate_permutation": perm,
        "top_candidate_bootstrap": boot,
        "top_candidate_metadata_r2": meta,
        "top_candidate_group_mortality": group_table.to_dict(orient="records"),
        "verdict": verdict,
        "outputs": {"pc_scores": str(pc_table), "candidate_groups": str(group_path), "json": str(json_path)},
        "ruo_claim_boundary": _ruo_claim_boundary(),
    }
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _load_matrix_and_obs(data_path: Path, metadata_keys: list[str | None] | None = None) -> tuple[pd.DataFrame, np.ndarray, int]:
    suffix = data_path.suffix.lower()
    if suffix == ".h5ad":
        a = ad.read_h5ad(data_path)
        X = np.asarray(a.X, dtype=float)
        return a.obs.copy(), X, int(a.n_vars)
    sep = "\t" if suffix in {".tsv", ".txt"} else ","
    table = pd.read_csv(data_path, sep=sep)
    metadata_key_set = {str(key) for key in (metadata_keys or []) if key}
    numeric = table.select_dtypes(include=[np.number])
    feature_cols = [col for col in numeric.columns if col not in metadata_key_set]
    obs_cols = [col for col in table.columns if col in metadata_key_set or col not in feature_cols]
    if numeric.empty:
        raise ValueError("Generic CSV/TSV discovery needs numeric feature columns.")
    if not feature_cols:
        raise ValueError("Generic CSV/TSV discovery needs numeric feature columns beyond metadata keys.")
    obs = table[obs_cols].copy()
    obs.index = table.index.astype(str)
    return obs, table[feature_cols].to_numpy(dtype=float), int(len(feature_cols))


def _generic_design_frame(
    obs: pd.DataFrame,
    treatment_key: str,
    outcome_key: str,
    covariate_keys: list[str],
    patient_id_key: str | None,
    batch_key: str | None,
    known_endotype_key: str | None,
) -> pd.DataFrame:
    required = [treatment_key, outcome_key]
    missing = [key for key in required if key not in obs.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    available_covars = [key for key in covariate_keys if key in obs.columns]
    for key in [batch_key, known_endotype_key]:
        if key and key in obs.columns and key not in available_covars:
            available_covars.append(key)

    df = pd.DataFrame(index=obs.index)
    df["outcome"] = pd.to_numeric(obs[outcome_key], errors="coerce")
    df["treatment"] = obs[treatment_key].astype(str)
    if patient_id_key and patient_id_key in obs.columns:
        df["patient_id"] = obs[patient_id_key].astype(str)

    for key in available_covars:
        series = obs[key]
        numeric = pd.to_numeric(series, errors="coerce")
        df[key] = numeric if numeric.notna().sum() >= max(3, len(series) // 3) else series.astype(str)

    df = df.dropna(subset=["outcome", "treatment"])
    df = df[df["treatment"].map(df["treatment"].value_counts()) >= 3]
    if df["treatment"].nunique() < 2:
        raise ValueError("Generic discovery requires at least two treatment groups.")
    if df["outcome"].nunique() < 2:
        raise ValueError("Generic discovery requires a binary or variable outcome.")
    return df


def _expression_pcs(
    X: np.ndarray,
    index: pd.Index,
    *,
    n_top_variable_features: int,
    n_pcs: int,
    random_seed: int,
) -> tuple[pd.DataFrame, dict[str, float]]:
    pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("var", VarianceThreshold()),
            ("scaler", StandardScaler()),
        ]
    )
    Xp = pipe.fit_transform(np.asarray(X, dtype=float))
    variances = np.var(Xp, axis=0)
    k = min(n_top_variable_features, Xp.shape[1])
    top = np.argsort(variances)[-k:]
    Xtop = Xp[:, top]
    n_components = min(n_pcs, Xtop.shape[0] - 2, Xtop.shape[1])
    pca = PCA(n_components=n_components, random_state=random_seed)
    scores = pca.fit_transform(Xtop)
    columns = [f"PC{i + 1}" for i in range(n_components)]
    pcdf = pd.DataFrame(scores, index=index, columns=columns)
    pcdf = (pcdf - pcdf.mean(axis=0)) / pcdf.std(axis=0, ddof=0)
    explained = {col: float(pca.explained_variance_ratio_[i]) for i, col in enumerate(columns)}
    return pcdf, explained


def _screen_generic_pcs(df: pd.DataFrame, pcdf: pd.DataFrame, covariate_keys: list[str]) -> list[dict[str, Any]]:
    data = pd.concat([df, pcdf], axis=1)
    rows = []
    for pc in pcdf.columns:
        try:
            rows.append(_fit_generic_interaction(data, pc, covariate_keys))
        except Exception as exc:
            rows.append({"pc": pc, "error": repr(exc)})
    valid = [row for row in rows if "error" not in row]
    if valid:
        qvals = _bh_fdr([row["lrt_p"] for row in valid])
        for row, qval in zip(valid, qvals):
            row["lrt_fdr_bh"] = float(qval)
    return rows


def _fit_generic_interaction(df: pd.DataFrame, pc: str, covariate_keys: list[str]) -> dict[str, Any]:
    covars = [key for key in covariate_keys if key in df.columns and df[key].nunique(dropna=True) > 1]
    covar_formula = " + ".join(_formula_term(df, key) for key in covars)
    suffix = f" + {covar_formula}" if covar_formula else ""
    full_formula = f"outcome ~ C(treatment) * {pc}{suffix}"
    reduced_formula = f"outcome ~ C(treatment) + {pc}{suffix}"
    full = smf.logit(full_formula, data=df).fit(disp=False, maxiter=300)
    reduced = smf.logit(reduced_formula, data=df).fit(disp=False, maxiter=300)
    terms = [term for term in full.params.index if ":" in term and "treatment" in term and pc in term]
    if not terms:
        raise KeyError({"available_terms": list(full.params.index), "pc": pc})
    term = min(terms, key=lambda item: float(full.pvalues[item]))
    beta = float(full.params[term])
    ci = full.conf_int().loc[term]
    lr = 2 * (full.llf - reduced.llf)
    return {
        "pc": pc,
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


def _generic_permutation(
    df: pd.DataFrame,
    pcdf: pd.DataFrame,
    pc: str,
    observed_lrt: float,
    covariate_keys: list[str],
    rng: np.random.Generator,
    permutation_n: int,
) -> dict[str, Any]:
    base = pd.concat([df, pcdf[[pc]]], axis=1)
    vals = []
    failures = 0
    for _ in range(permutation_n):
        d = base.copy()
        shuffled = d[pc].to_numpy().copy()
        rng.shuffle(shuffled)
        d[pc] = shuffled
        try:
            vals.append(_fit_generic_interaction(d, pc, covariate_keys)["lrt"])
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


def _generic_bootstrap(
    df: pd.DataFrame,
    pcdf: pd.DataFrame,
    pc: str,
    covariate_keys: list[str],
    rng: np.random.Generator,
    bootstrap_n: int,
) -> dict[str, Any]:
    base = pd.concat([df, pcdf[[pc]]], axis=1)
    betas = []
    ors = []
    pvals = []
    failures = 0
    for _ in range(bootstrap_n):
        idx = rng.choice(np.arange(len(base)), size=len(base), replace=True)
        d = base.iloc[idx].copy()
        if d["treatment"].nunique() < 2 or d["outcome"].nunique() < 2:
            failures += 1
            continue
        try:
            res = _fit_generic_interaction(d, pc, covariate_keys)
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


def _generic_metadata_r2(
    df: pd.DataFrame,
    pcdf: pd.DataFrame,
    pc: str,
    covariate_keys: list[str],
    batch_key: str | None,
    known_endotype_key: str | None,
) -> dict[str, Any]:
    data = pd.concat([df, pcdf[[pc]]], axis=1)
    covars = [key for key in list(covariate_keys) + [batch_key, known_endotype_key] if key and key in data.columns and data[key].nunique(dropna=True) > 1]
    if not covars:
        return {"pc": pc, "r2": 0.0, "adj_r2": 0.0, "model_p": np.nan, "note": "no_metadata_covariates_supplied"}
    formula = f"{pc} ~ " + " + ".join(_formula_term(data, key) for key in dict.fromkeys(covars))
    try:
        model = smf.ols(formula, data=data).fit()
        return {"pc": pc, "r2": float(model.rsquared), "adj_r2": float(model.rsquared_adj), "model_p": float(model.f_pvalue) if model.f_pvalue is not None else np.nan}
    except Exception as exc:
        return {"pc": pc, "error": repr(exc)}


def _generic_group_table(df: pd.DataFrame, pcdf: pd.DataFrame, pc: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.concat([df, pcdf[[pc]]], axis=1).copy()
    data["candidate_endotype"] = np.where(data[pc] >= float(data[pc].median()), f"{pc}_high", f"{pc}_low")
    table = data.groupby(["candidate_endotype", "treatment"], observed=False)["outcome"].agg(["count", "sum", "mean"]).reset_index()
    return data, table


def _formula_term(df: pd.DataFrame, key: str) -> str:
    return key if pd.api.types.is_numeric_dtype(df[key]) else f"C({key})"


def _bh_fdr(pvals: list[float]) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def _normalize_adapter(dataset_adapter: str | None) -> str | None:
    return dataset_adapter.strip().lower().replace("-", "_").replace(" ", "_") if dataset_adapter else None


def _ruo_claim_boundary() -> str:
    return "Discovery evidence is RUO only and requires locked external validation before any biological or clinical claim is certified."
