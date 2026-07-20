from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2

PC = Path("results/vanish_denovo_vasopressin_pc_scores.csv")
OUT = Path("results/vanish_pc11_independence_challenge.json")
TABLE = Path("results/vanish_pc11_independence_challenge_tables.txt")

KEY = "C(vasopressor)[T.Vasopressin]:PC11"

def fit(df, name, formula):
    full = smf.logit(formula, data=df).fit(disp=False, maxiter=500)

    terms = [t for t in full.params.index if ":" in t and "vasopressor" in t.lower() and "PC11" in t]
    if KEY in full.params.index:
        term = KEY
    elif terms:
        term = terms[0]
    else:
        raise KeyError(list(full.params.index))

    beta = float(full.params[term])
    ci = full.conf_int().loc[term]

    return {
        "name": name,
        "formula": formula,
        "term": term,
        "beta": beta,
        "or_per_1sd": float(np.exp(beta)),
        "p_value": float(full.pvalues[term]),
        "ci_low_or": float(np.exp(ci[0])),
        "ci_high_or": float(np.exp(ci[1])),
        "llf": float(full.llf),
        "available_terms": list(full.params.index),
    }

def main():
    df = pd.read_csv(PC)

    df = df.dropna(subset=["death", "vasopressor", "steroid", "srs", "age", "apache", "sex", "PC11"])
    df = df[df["vasopressor"].isin(["Noradrenaline", "Vasopressin"])]
    df = df[df["steroid"].isin(["Placebo", "Hydrocortisone"])]
    df = df[df["srs"].isin(["SRS1", "SRS2"])]

    df["vasopressor"] = pd.Categorical(df["vasopressor"], categories=["Noradrenaline", "Vasopressin"])
    df["steroid"] = pd.Categorical(df["steroid"], categories=["Placebo", "Hydrocortisone"])
    df["srs"] = pd.Categorical(df["srs"], categories=["SRS1", "SRS2"])
    df["sex"] = pd.Categorical(df["sex"])

    formulas = {
        "base_current": "death ~ C(vasopressor) * PC11 + C(steroid) + C(srs) + age + apache + C(sex)",
        "controls_known_steroid_srs_interaction": "death ~ C(vasopressor) * PC11 + C(steroid) * C(srs) + age + apache + C(sex)",
        "controls_vasopressor_srs_interaction": "death ~ C(vasopressor) * PC11 + C(vasopressor) * C(srs) + C(steroid) + age + apache + C(sex)",
        "controls_both_known_interactions": "death ~ C(vasopressor) * PC11 + C(steroid) * C(srs) + C(vasopressor) * C(srs) + age + apache + C(sex)",
        "controls_steroid_srs_and_comorbidities": "death ~ C(vasopressor) * PC11 + C(steroid) * C(srs) + age + apache + C(sex) + diabetes + immunocompromise + cancer + copd + renal_failure",
    }

    results = {}
    lines = []
    lines.append("PC11 independence challenge")
    lines.append("=" * 100)
    lines.append(f"N = {len(df)}")
    lines.append("")
    lines.append("Group mortality: PC11 high/low × vasopressor × steroid")
    df["pc11_group"] = np.where(df["PC11"] >= df["PC11"].median(), "PC11_high", "PC11_low")
    tab = df.groupby(["pc11_group", "vasopressor", "steroid"], observed=False)["death"].agg(["count", "sum", "mean"]).reset_index()
    lines.append(tab.to_string(index=False))

    for name, formula in formulas.items():
        try:
            res = fit(df, name, formula)
            results[name] = res
            lines.append("")
            lines.append("-" * 100)
            lines.append(name)
            lines.append(formula)
            lines.append(f"term={res['term']}")
            lines.append(f"OR={res['or_per_1sd']:.4g}, p={res['p_value']:.4g}, CI=({res['ci_low_or']:.4g}, {res['ci_high_or']:.4g})")
        except Exception as e:
            results[name] = {"error": repr(e), "formula": formula}
            lines.append("")
            lines.append("-" * 100)
            lines.append(name)
            lines.append("ERROR: " + repr(e))

    verdict = {}
    hard = results.get("controls_both_known_interactions", {})
    if "p_value" in hard and hard["p_value"] < 0.05:
        verdict["pc11_independent_of_known_srs_interactions"] = "passes"
    else:
        verdict["pc11_independent_of_known_srs_interactions"] = "not_confirmed"

    results_out = {
        "test": "PC11 independence challenge against known SRS/steroid and SRS/vasopressor interactions",
        "n": int(len(df)),
        "group_mortality": tab.to_dict(orient="records"),
        "models": results,
        "verdict": verdict,
        "warning": "Discovery-stage result only. Requires gene annotation and external validation.",
    }

    OUT.write_text(json.dumps(results_out, indent=2))
    TABLE.write_text("\n".join(lines))

    print("\n".join(lines))
    print()
    print("Saved:", OUT)
    print("Saved:", TABLE)

if __name__ == "__main__":
    main()
