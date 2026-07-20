from pathlib import Path
import json
import pandas as pd
import numpy as np

OUT = Path("results/sepsis_precisiontx_audit")
OUT.mkdir(parents=True, exist_ok=True)

VANISH_DEEP = Path("results/vanish_steroid_safety_gate_deep_audit.json")
VANISH_SIMPLE = Path("results/vanish_steroid_srs_interaction_test.json")
GAINS = Path("results/sepsis_precisiontx_audit/gains_external_supportive_validation.json")

def load(p):
    if not p.exists():
        raise FileNotFoundError(p)
    return json.loads(p.read_text())

def fmt(x, digits=4):
    if x is None:
        return "NA"
    try:
        return f"{float(x):.{digits}g}"
    except Exception:
        return str(x)

vanish = load(VANISH_DEEP)
simple = load(VANISH_SIMPLE)
gains = load(GAINS)

v_int = vanish["interaction_adjusted_full"]
v_perm = vanish["interaction_permutation_lrt"]
v_boot = vanish["interaction_bootstrap"]
v_mort = vanish["tables"]["mortality_rates"]

g_comb = gains["combined"]
g_srs = g_comb["srs_vs_mortality_adjusted_study"]

# Extract mortality rates
def mortality_rate(rows, srs, steroid=None):
    for r in rows:
        if r.get("srs") == srs and (steroid is None or r.get("steroid") == steroid):
            return r
    return None

srs2_placebo = mortality_rate(v_mort, "SRS2", "Placebo")
srs2_hydro = mortality_rate(v_mort, "SRS2", "Hydrocortisone")
srs1_placebo = mortality_rate(v_mort, "SRS1", "Placebo")
srs1_hydro = mortality_rate(v_mort, "SRS1", "Hydrocortisone")

pack = {
    "title": "OmicsTrust Steroid Safety Gate Evidence Pack",
    "scope": "Septic shock transcriptomic endotype audit focused on SRS and hydrocortisone-associated mortality heterogeneity.",
    "claim_level": "Strong internal treatment-by-endotype signal with external supportive endotype biology; not direct external treatment validation.",
    "not_clinical_guidance": True,

    "vanish_internal_treatment_signal": {
        "n_patients": vanish["n_patients"],
        "question": vanish["medical_question"],
        "srs2_placebo_mortality": srs2_placebo,
        "srs2_hydrocortisone_mortality": srs2_hydro,
        "srs1_placebo_mortality": srs1_placebo,
        "srs1_hydrocortisone_mortality": srs1_hydro,
        "adjusted_interaction_or": v_int["interaction_or"],
        "adjusted_interaction_wald_p": v_int["interaction_wald_p"],
        "adjusted_interaction_lrt_p": v_int["interaction_lrt_p"],
        "permutation_p": v_perm["permutation_p_lrt_ge_observed"],
        "bootstrap_prop_beta_positive": v_boot["prop_beta_positive"],
        "bootstrap_or_median": v_boot["or_median"],
        "metadata_only_srs_auc": vanish["metadata_only_predicts_srs"]["observed"]["roc_auc"],
        "expression_predicts_srs_balanced_accuracy": vanish["expression_predicts_srs"]["observed"]["balanced_accuracy"]
    },

    "gains_external_supportive_biology": {
        "scope": gains["scope"],
        "combined_n": g_comb["n"],
        "study_counts": g_comb["study_counts"],
        "srs_counts": g_comb["srs_counts"],
        "death_rate_by_srs": g_comb["death_rate_by_srs"],
        "srs_vs_mortality_adjusted_for_study": g_srs,
        "pc11_external_result": {
            "pc11_vs_srs_auc": g_comb["pc11_vs_srs_auc"],
            "pc11_vs_srs_mannwhitney_p": g_comb["pc11_vs_srs_mannwhitney_p"],
            "pc11_vs_mortality_adjusted_srs_study": g_comb["pc11_vs_mortality_adjusted_srs_study"]
        }
    },

    "audit_verdict": {
        "srs_endotype_biology": "externally_supported",
        "hydrocortisone_srs2_interaction": "strong_internal_signal",
        "direct_external_treatment_validation": "not_available_in_GAinS_due_to_absent_treatment_labels",
        "pc11": "vanish_internal_candidate_only; no GAinS supportive mortality/SRS evidence",
        "overall": "best_current_omicsTrust_opportunity"
    },

    "safe_research_wording": (
        "VANISH shows a strong internal hydrocortisone-by-SRS interaction on 28-day mortality, "
        "with higher observed mortality among SRS2 patients receiving hydrocortisone versus placebo. "
        "GAinS external cohorts support SRS as a reproducible mortality-associated sepsis biology, "
        "but do not provide hydrocortisone exposure labels; therefore, this remains RUO evidence, "
        "not treatment guidance."
    ),

    "ruo_note": "Research-use audit only. Not diagnostic, not clinical decision support, and not a treatment recommendation."
}

json_path = OUT / "steroid_safety_gate_evidence_pack.json"
json_path.write_text(json.dumps(pack, indent=2))

md = f"""# OmicsTrust Steroid Safety Gate Evidence Pack

## Scope

Septic shock transcriptomic endotype audit focused on **SRS** and hydrocortisone-associated mortality heterogeneity.

**Use:** research audit only.  
**Not:** diagnosis, clinical decision support, or treatment recommendation.

---

## 1. VANISH internal treatment-by-endotype signal

**Question:** Does SRS endotype identify septic shock patients with possible hydrocortisone-associated mortality heterogeneity?

- VANISH n = **{vanish["n_patients"]}**
- SRS2 placebo mortality = **{fmt(srs2_placebo["mean"] * 100, 3)}%** ({srs2_placebo["sum"]}/{srs2_placebo["count"]})
- SRS2 hydrocortisone mortality = **{fmt(srs2_hydro["mean"] * 100, 3)}%** ({srs2_hydro["sum"]}/{srs2_hydro["count"]})
- Adjusted interaction OR = **{fmt(v_int["interaction_or"], 4)}**
- Wald p = **{fmt(v_int["interaction_wald_p"], 4)}**
- LRT p = **{fmt(v_int["interaction_lrt_p"], 4)}**
- Permutation p = **{fmt(v_perm["permutation_p_lrt_ge_observed"], 4)}**
- Bootstrap beta-positive proportion = **{fmt(v_boot["prop_beta_positive"], 4)}**

**Interpretation:** strong internal hydrocortisone × SRS2 mortality signal.

---

## 2. SRS is not metadata leakage

- Metadata-only SRS prediction AUC = **{fmt(vanish["metadata_only_predicts_srs"]["observed"]["roc_auc"], 4)}**
- Expression-based SRS balanced accuracy = **{fmt(vanish["expression_predicts_srs"]["observed"]["balanced_accuracy"], 4)}**

**Interpretation:** SRS behaves like a transcriptomic biology rather than a simple metadata artifact.

---

## 3. GAinS external supportive biology

GAinS cohorts did not contain hydrocortisone exposure labels, so this is **not direct external treatment validation**.

But they do test whether SRS biology transfers outside VANISH.

- Combined GAinS n = **{g_comb["n"]}**
- E-MTAB-4421 n = **{g_comb["study_counts"].get("E-MTAB-4421")}**
- E-MTAB-4451 n = **{g_comb["study_counts"].get("E-MTAB-4451")}**
- SRS1 death rate = **{fmt(g_comb["death_rate_by_srs"][0]["mean"] * 100, 3)}%**
- SRS2 death rate = **{fmt(g_comb["death_rate_by_srs"][1]["mean"] * 100, 3)}%**
- SRS2 vs SRS1 mortality OR adjusted for study = **{fmt(g_srs["or"], 4)}**
- p = **{fmt(g_srs["p"], 4)}**

**Interpretation:** external cohorts support SRS as reproducible mortality-associated sepsis biology.

---

## 4. PC11 status

PC11 was strong inside VANISH as a vasopressin-response interaction axis, but GAinS lacks vasopressin/noradrenaline treatment labels.

- GAinS PC11 vs SRS AUC = **{fmt(g_comb["pc11_vs_srs_auc"], 4)}**
- GAinS PC11 vs SRS p = **{fmt(g_comb["pc11_vs_srs_mannwhitney_p"], 4)}**
- GAinS PC11 vs mortality adjusted p = **{fmt(g_comb["pc11_vs_mortality_adjusted_srs_study"]["p"], 4)}**

**Interpretation:** PC11 remains a VANISH-internal treatment-response candidate. It needs a dataset with vasopressin/noradrenaline exposure labels.

---

## Evidence grade

| Layer | Result |
|---|---|
| SRS biology | Externally supported |
| Hydrocortisone × SRS2 | Strong internal signal |
| Direct external treatment validation | Not available in GAinS |
| PC11 external support | Not detected in GAinS |
| Current best OmicsTrust direction | Steroid Safety Gate |

---

## Safe research wording

VANISH shows a strong internal hydrocortisone-by-SRS interaction on 28-day mortality, with higher observed mortality among SRS2 patients receiving hydrocortisone versus placebo. GAinS external cohorts support SRS as a reproducible mortality-associated sepsis biology, but do not provide hydrocortisone exposure labels; therefore, this remains RUO evidence, not treatment guidance.

---

## Bottom line

The best current OmicsTrust opportunity is:

**Steroid Safety Gate for septic shock endotype auditing**

Not a treatment recommendation.  
Not clinical decision support.  
A research audit framework for identifying treatment-by-endotype safety signals that require prospective validation.
"""

md_path = OUT / "steroid_safety_gate_evidence_pack.md"
md_path.write_text(md)

print(md)
print("\\nWROTE:")
print(json_path)
print(md_path)
