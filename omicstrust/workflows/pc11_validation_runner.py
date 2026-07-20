from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any


CLAIM_BOUNDARY = {
    "allowed": [
        "locked PC11 score computed in external cohort",
        "gene coverage audit",
        "descriptive mortality association",
        "descriptive vasopressor interaction if metadata exists",
        "external validation evidence table",
    ],
    "not_allowed": [
        "treatment efficacy proven",
        "treatment safety proven",
        "clinical treatment recommendation",
        "bedside vasopressor selection",
        "dosing guidance",
        "diagnostic device claim",
        "regulatory readiness claim",
    ],
}


def run_pc11_validation(
    contract: str | Path,
    expression: str | Path,
    metadata: str | Path,
    *,
    output: str | Path = "results/pc11_validation_run",
    cohort_id: str = "external_cohort",
    sample_id_column: str = "sample_id",
    outcome_column: str | None = None,
    treatment_column: str | None = None,
    treatment_active_value: str = "vasopressin",
    treatment_reference_value: str = "norepinephrine",
    endotype_cohort_column: str = "endotype_cohort",
    endotype_class_column: str = "endotype_class",
) -> dict[str, Any]:
    """Run locked PC11 validation on a harmonized sample-by-gene expression CSV.

    Expected expression format:
      sample_id,PDIA6,LILRB1,...,GBP4

    Metadata format:
      sample_id,outcome,treatment,...

    This is a validation/audit runner. It does not prove treatment efficacy, safety,
    dosing, clinical utility, or regulatory readiness.
    """

    contract_payload = _read_json(Path(contract))
    expr_rows = _read_csv(Path(expression))
    meta_rows = _read_csv(Path(metadata))

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)

    meta_by_id = {str(r.get(sample_id_column, "")): r for r in meta_rows}
    merged = []
    for row in expr_rows:
        sid = str(row.get(sample_id_column, ""))
        if sid in meta_by_id:
            merged.append({"sample_id": sid, "expression": row, "metadata": meta_by_id[sid]})

    if not merged:
        raise ValueError("No overlapping sample IDs between expression and metadata.")

    pos_genes = contract_payload.get("positive_direction_genes", [])
    neg_genes = contract_payload.get("negative_direction_genes", [])
    all_genes = list(dict.fromkeys(pos_genes + neg_genes))

    gene_values = _extract_gene_values(merged, all_genes)
    zscores = _zscore_gene_values(gene_values)

    score_rows = []
    for item in merged:
        sid = item["sample_id"]
        pos = [_safe_get(zscores.get(g, {}), sid) for g in pos_genes]
        neg = [_safe_get(zscores.get(g, {}), sid) for g in neg_genes]
        pos = [v for v in pos if v is not None]
        neg = [v for v in neg if v is not None]
        score = (mean(pos) if pos else 0.0) - (mean(neg) if neg else 0.0)
        score_rows.append(
            {
                "sample_id": sid,
                "pc11_locked_score": round(score, 6),
                "positive_gene_count": len(pos),
                "negative_gene_count": len(neg),
                "detected_gene_count": len(pos) + len(neg),
            }
        )

    scores_by_id = {r["sample_id"]: r["pc11_locked_score"] for r in score_rows}
    coverage = _coverage_report(contract_payload, gene_values, len(merged))
    score_summary = _score_summary(score_rows)

    outcome_report = None
    if outcome_column:
        outcome_report = _outcome_association(score_rows, meta_by_id, sample_id_column, outcome_column)

    treatment_report = None
    if outcome_column and treatment_column:
        treatment_report = _treatment_interaction_descriptive(
            score_rows,
            meta_by_id,
            sample_id_column,
            outcome_column,
            treatment_column,
            treatment_active_value,
            treatment_reference_value,
        )

    formal_validation_stats = None
    if outcome_column:
        formal_validation_stats = _formal_validation_stats(score_rows, meta_by_id, outcome_column, endotype_cohort_column)

    endotype_structure_review = None
    if endotype_class_column and any(row.get(endotype_class_column) for row in meta_rows):
        endotype_structure_review = _endotype_structure_review(score_rows, meta_by_id, endotype_class_column)

    conclusion = _validation_conclusion(
        cohort_id=cohort_id,
        coverage=coverage,
        outcome_report=outcome_report,
        formal_stats=formal_validation_stats,
        endotype_review=endotype_structure_review,
        treatment_report=treatment_report,
        treatment_column=treatment_column,
    )

    report = {
        "workflow": "pc11_validation_runner",
        "status": "completed",
        "cohort_id": cohort_id,
        "n_expression_rows": len(expr_rows),
        "n_metadata_rows": len(meta_rows),
        "n_matched_samples": len(merged),
        "locked_axis_contract_id": contract_payload.get("contract_id"),
        "axis_name": contract_payload.get("axis_name"),
        "scoring_rule": contract_payload.get("scoring_rule", {}),
        "gene_coverage": coverage,
        "score_summary": score_summary,
        "outcome_association": outcome_report,
        "treatment_interaction_descriptive": treatment_report,
        "formal_validation_stats": formal_validation_stats,
        "endotype_structure_review": endotype_structure_review,
        "validation_conclusion": conclusion,
        "claim_boundary": CLAIM_BOUNDARY,
        "verdict": {
            "pc11_score_computable": coverage["passes_minimum_gene_coverage"],
            "external_validation_status": "computed_requires_scientific_review",
            "treatment_guidance_allowed": False,
            "clinical_use_allowed": False,
            "therapeutic_claim_allowed": False,
            "regulatory_ready": False,
        },
    }

    _write_csv(out / "pc11_sample_scores.csv", score_rows)
    _write_json(out / "pc11_gene_coverage.json", coverage)
    _write_json(out / "pc11_score_summary.json", score_summary)
    _write_json(out / "pc11_outcome_association.json", outcome_report or {})
    _write_json(out / "pc11_treatment_interaction_descriptive.json", treatment_report or {})
    _write_json(out / "pc11_formal_validation_stats.json", formal_validation_stats or {})
    _write_json(out / "pc11_endotype_structure_review.json", endotype_structure_review or {})
    _write_json(out / "pc11_external_validation_conclusion.json", conclusion)
    _write_json(out / "pc11_validation_run_report.json", report)
    _write_markdown(out / "pc11_validation_run_summary.md", report)
    _write_conclusion_markdown(out / "PC11_EXTERNAL_VALIDATION_CONCLUSION.md", report)

    report["report_links"] = {
        "sample_scores": str(out / "pc11_sample_scores.csv"),
        "gene_coverage": str(out / "pc11_gene_coverage.json"),
        "score_summary": str(out / "pc11_score_summary.json"),
        "outcome_association": str(out / "pc11_outcome_association.json"),
        "treatment_interaction_descriptive": str(out / "pc11_treatment_interaction_descriptive.json"),
        "formal_validation_stats": str(out / "pc11_formal_validation_stats.json"),
        "endotype_structure_review": str(out / "pc11_endotype_structure_review.json"),
        "external_validation_conclusion": str(out / "PC11_EXTERNAL_VALIDATION_CONCLUSION.md"),
        "validation_run_report": str(out / "pc11_validation_run_report.json"),
        "summary_markdown": str(out / "pc11_validation_run_summary.md"),
    }
    _write_json(out / "pc11_validation_run_report.json", report)
    return report


def _extract_gene_values(merged: list[dict[str, Any]], genes: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for gene in genes:
        values = {}
        for item in merged:
            sid = item["sample_id"]
            raw = item["expression"].get(gene)
            val = _to_float(raw)
            if val is not None:
                values[sid] = val
        if values:
            out[gene] = values
    return out


def _zscore_gene_values(gene_values: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out = {}
    for gene, values in gene_values.items():
        vals = list(values.values())
        mu = mean(vals)
        sd = _std(vals)
        if sd == 0:
            out[gene] = {sid: 0.0 for sid in values}
        else:
            out[gene] = {sid: (v - mu) / sd for sid, v in values.items()}
    return out


def _coverage_report(contract: dict[str, Any], gene_values: dict[str, dict[str, float]], n_samples: int) -> dict[str, Any]:
    pos = contract.get("positive_direction_genes", [])
    neg = contract.get("negative_direction_genes", [])
    detected = sorted(gene_values.keys())
    min_required = int(contract.get("scoring_rule", {}).get("minimum_detected_genes_required", 8))
    return {
        "n_samples": n_samples,
        "positive_genes_requested": len(pos),
        "negative_genes_requested": len(neg),
        "positive_genes_detected": [g for g in pos if g in gene_values],
        "negative_genes_detected": [g for g in neg if g in gene_values],
        "detected_gene_count": len(detected),
        "minimum_detected_genes_required": min_required,
        "passes_minimum_gene_coverage": len(detected) >= min_required and any(g in gene_values for g in pos) and any(g in gene_values for g in neg),
        "missing_genes": [g for g in pos + neg if g not in gene_values],
    }


def _score_summary(score_rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(r["pc11_locked_score"]) for r in score_rows]
    return {
        "n": len(scores),
        "mean": round(mean(scores), 6),
        "median": round(median(scores), 6),
        "min": round(min(scores), 6),
        "max": round(max(scores), 6),
        "sd": round(_std(scores), 6),
        "q25": round(_quantile(scores, 0.25), 6),
        "q75": round(_quantile(scores, 0.75), 6),
    }


def _outcome_association(score_rows, meta_by_id, sample_id_column, outcome_column):
    evaluable = []
    for r in score_rows:
        sid = r["sample_id"]
        outcome = _binary_outcome(meta_by_id[sid].get(outcome_column))
        if outcome is None:
            continue
        evaluable.append((float(r["pc11_locked_score"]), outcome))

    if not evaluable:
        return {
            "outcome_column": outcome_column,
            "mortality_evaluable_n": 0,
            "interpretation_boundary": "No binary outcome values were evaluable.",
        }

    median_score = median([score for score, _ in evaluable])
    high = []
    low = []
    for score, outcome in evaluable:
        if score >= median_score:
            high.append(outcome)
        else:
            low.append(outcome)

    high_events = sum(high)
    low_events = sum(low)
    high_n = len(high)
    low_n = len(low)

    return {
        "outcome_column": outcome_column,
        "mortality_evaluable_n": len(evaluable),
        "median_score_cutpoint": round(median_score, 6),
        "pc11_high_events": high_events,
        "pc11_high_n": high_n,
        "pc11_high_event_rate": round(high_events / high_n, 6) if high_n else None,
        "pc11_low_events": low_events,
        "pc11_low_n": low_n,
        "pc11_low_event_rate": round(low_events / low_n, 6) if low_n else None,
        "odds_ratio_high_vs_low": _odds_ratio(high_events, high_n - high_events, low_events, low_n - low_events),
        "interpretation_boundary": "Descriptive validation statistic only; not clinical utility, treatment selection, or causality.",
    }


def _treatment_interaction_descriptive(score_rows, meta_by_id, sample_id_column, outcome_column, treatment_column, active, reference):
    active_l = str(active).lower()
    ref_l = str(reference).lower()
    evaluable = []
    for r in score_rows:
        sid = r["sample_id"]
        outcome = _binary_outcome(meta_by_id[sid].get(outcome_column))
        treatment = str(meta_by_id[sid].get(treatment_column, "")).lower()
        if outcome is None or treatment not in {active_l, ref_l}:
            continue
        evaluable.append((float(r["pc11_locked_score"]), outcome, treatment))

    median_score = median([score for score, _, _ in evaluable]) if evaluable else median([float(r["pc11_locked_score"]) for r in score_rows])
    cells = {
        "high_active": [],
        "high_reference": [],
        "low_active": [],
        "low_reference": [],
    }

    for score, outcome, treatment in evaluable:
        group = "high" if score >= median_score else "low"
        if treatment == active_l:
            cells[f"{group}_active"].append(outcome)
        elif treatment == ref_l:
            cells[f"{group}_reference"].append(outcome)

    summary = {}
    for key, vals in cells.items():
        events = sum(vals)
        n = len(vals)
        summary[key] = {
            "events": events,
            "n": n,
            "event_rate": round(events / n, 6) if n else None,
        }

    ha = summary["high_active"]
    hr = summary["high_reference"]
    la = summary["low_active"]
    lr = summary["low_reference"]

    high_or = _odds_ratio(ha["events"], ha["n"] - ha["events"], hr["events"], hr["n"] - hr["events"]) if ha["n"] and hr["n"] else None
    low_or = _odds_ratio(la["events"], la["n"] - la["events"], lr["events"], lr["n"] - lr["events"]) if la["n"] and lr["n"] else None

    interaction_ratio = None
    if high_or and low_or and low_or["or"] not in (0, None):
        interaction_ratio = round(high_or["or"] / low_or["or"], 6)

    return {
        "treatment_column": treatment_column,
        "active_value": active,
        "reference_value": reference,
        "treatment_evaluable_n": len(evaluable),
        "median_score_cutpoint": round(median_score, 6),
        "cells": summary,
        "active_vs_reference_or_in_pc11_high": high_or,
        "active_vs_reference_or_in_pc11_low": low_or,
        "descriptive_interaction_ratio": interaction_ratio,
        "matches_vanish_direction_if_less_than_1": interaction_ratio is not None and interaction_ratio < 1,
        "interpretation_boundary": "Descriptive only; requires randomized or carefully adjusted treatment metadata and sensitivity analysis.",
    }


def _formal_validation_stats(score_rows, meta_by_id, outcome_column, endotype_cohort_column):
    evaluable = []
    for r in score_rows:
        sid = r["sample_id"]
        outcome = _binary_outcome(meta_by_id[sid].get(outcome_column))
        if outcome is None:
            continue
        evaluable.append(
            {
                "sample_id": sid,
                "score": float(r["pc11_locked_score"]),
                "outcome": outcome,
                "endotype_cohort": str(meta_by_id[sid].get(endotype_cohort_column, "")).strip(),
            }
        )

    if not evaluable:
        return {
            "outcome_column": outcome_column,
            "mortality_evaluable_n": 0,
            "interpretation": "No evaluable binary outcome values were found.",
        }

    scores = [row["score"] for row in evaluable]
    score_z = _zscore_vector(scores)
    y = [row["outcome"] for row in evaluable]
    model_1 = _logistic_regression_rows(y, {"pc11_z": score_z})

    cohort_values = sorted({row["endotype_cohort"] for row in evaluable if row["endotype_cohort"]})
    model_2 = None
    if len(cohort_values) == 2:
        reference, active = cohort_values[0], cohort_values[1]
        cohort_dummy = [1.0 if row["endotype_cohort"] == active else 0.0 for row in evaluable]
        model_2 = _logistic_regression_rows(y, {"pc11_z": score_z, f"cohort_{active}": cohort_dummy})

    alive = [row["score"] for row in evaluable if row["outcome"] == 0]
    dead = [row["score"] for row in evaluable if row["outcome"] == 1]
    return {
        "outcome_column": outcome_column,
        "mortality_evaluable_n": len(evaluable),
        "events": int(sum(y)),
        "event_rate": round(sum(y) / len(y), 6),
        "model_1_death_pc11_z": model_1,
        "model_2_death_pc11_z_plus_endotype_cohort": model_2,
        "pc11_by_survival": {
            "alive_n": len(alive),
            "alive_median": round(median(alive), 6) if alive else None,
            "alive_mean": round(mean(alive), 6) if alive else None,
            "dead_n": len(dead),
            "dead_median": round(median(dead), 6) if dead else None,
            "dead_mean": round(mean(dead), 6) if dead else None,
        },
        "claim_boundary": "External validation statistics only; not treatment selection, treatment efficacy, or clinical utility.",
    }


def _endotype_structure_review(score_rows, meta_by_id, endotype_class_column):
    groups: dict[str, list[float]] = {}
    for r in score_rows:
        sid = r["sample_id"]
        cls = str(meta_by_id[sid].get(endotype_class_column, "")).strip()
        if not cls:
            continue
        groups.setdefault(cls, []).append(float(r["pc11_locked_score"]))

    if len(groups) < 2:
        return {
            "endotype_class_column": endotype_class_column,
            "status": "not_evaluable",
            "reason": "Fewer than two endotype classes were available.",
        }

    all_scores = [score for values in groups.values() for score in values]
    grand_mean = mean(all_scores)
    ss_between = sum(len(values) * (mean(values) - grand_mean) ** 2 for values in groups.values())
    ss_total = sum((score - grand_mean) ** 2 for score in all_scores)
    ss_within = ss_total - ss_between
    df_between = len(groups) - 1
    df_within = len(all_scores) - len(groups)
    ms_between = ss_between / df_between if df_between else 0.0
    ms_within = ss_within / df_within if df_within else 0.0
    f_stat = ms_between / ms_within if ms_within else None
    eta_squared = ss_between / ss_total if ss_total else 0.0

    group_rows = [
        {
            "endotype_class": cls,
            "n": len(values),
            "median_pc11": round(median(values), 6),
            "mean_pc11": round(mean(values), 6),
            "sd_pc11": round(_std(values), 6),
        }
        for cls, values in sorted(groups.items())
    ]

    pairwise = []
    classes = sorted(groups)
    for i, class_a in enumerate(classes):
        for class_b in classes[i + 1 :]:
            a = groups[class_a]
            b = groups[class_b]
            pooled = _pooled_sd(a, b)
            d = (mean(a) - mean(b)) / pooled if pooled else None
            pairwise.append(
                {
                    "class_a": class_a,
                    "class_b": class_b,
                    "mean_a": round(mean(a), 6),
                    "mean_b": round(mean(b), 6),
                    "cohens_d_a_minus_b": round(d, 6) if d is not None else None,
                }
            )

    return {
        "endotype_class_column": endotype_class_column,
        "n": len(all_scores),
        "eta_squared": round(eta_squared, 6),
        "f_statistic": round(f_stat, 6) if f_stat is not None else None,
        "groups": group_rows,
        "pairwise_effects": pairwise,
        "interpretation": "Endotype structure validation only; not treatment-response validation.",
    }


def _validation_conclusion(*, cohort_id, coverage, outcome_report, formal_stats, endotype_review, treatment_report, treatment_column):
    mortality_grade = "NOT_EVALUATED"
    if formal_stats and formal_stats.get("model_1_death_pc11_z"):
        pc11_row = next((row for row in formal_stats["model_1_death_pc11_z"] if row.get("term") == "pc11_z"), None)
        if pc11_row and pc11_row.get("p") is not None and pc11_row["p"] < 0.05:
            mortality_grade = "SUPPORTED"
        elif outcome_report and outcome_report.get("odds_ratio_high_vs_low"):
            or_value = outcome_report["odds_ratio_high_vs_low"].get("or")
            mortality_grade = "WEAK_DIRECTIONAL_NOT_SIGNIFICANT" if or_value is not None and or_value < 1 else "NOT_SUPPORTED"

    endotype_grade = "NOT_EVALUATED"
    if endotype_review and endotype_review.get("eta_squared") is not None:
        endotype_grade = "PASS" if endotype_review["eta_squared"] >= 0.14 else "WEAK"

    treatment_grade = "NOT_EVALUATED"
    if treatment_report:
        n = sum(cell.get("n", 0) for cell in treatment_report.get("cells", {}).values())
        treatment_grade = "DESCRIPTIVE_ONLY" if n else "NOT_EVALUABLE_NO_TREATMENT_METADATA"
    elif treatment_column:
        treatment_grade = "NOT_EVALUABLE_NO_TREATMENT_METADATA"

    return {
        "cohort_id": cohort_id,
        "pc11_computability": "PASS" if coverage.get("passes_minimum_gene_coverage") else "FAIL",
        "gene_coverage": "PASS" if coverage.get("passes_minimum_gene_coverage") else "FAIL",
        "external_biology_endotype_structure": endotype_grade,
        "mortality_association": mortality_grade,
        "vasopressin_response_replication": treatment_grade,
        "drug_claim": "NOT_ALLOWED",
        "clinical_use": "NOT_ALLOWED",
        "regulatory_readiness": "NOT_ALLOWED",
        "summary": (
            "Locked PC11 is computable externally and can support biology/endotype validation if endotype structure is present. "
            "Treatment-response replication requires usable vasopressor metadata."
        ),
    }


def _logistic_regression_rows(y_values, predictors):
    try:
        import numpy as np
    except Exception:
        return [{"term": "model_error", "error": "numpy_unavailable"}]

    y = np.asarray(y_values, dtype=float)
    names = ["intercept", *predictors.keys()]
    x_cols = [np.ones(len(y))]
    for values in predictors.values():
        x_cols.append(np.asarray(values, dtype=float))
    x = np.column_stack(x_cols)
    beta = np.zeros(x.shape[1])
    converged = False
    for _ in range(100):
        eta = np.clip(x @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1.0 - p), 1e-8, None)
        z = eta + (y - p) / w
        xtw = x.T * w
        beta_new = np.linalg.pinv(xtw @ x) @ (xtw @ z)
        if np.max(np.abs(beta_new - beta)) < 1e-8:
            beta = beta_new
            converged = True
            break
        beta = beta_new

    eta = np.clip(x @ beta, -30, 30)
    p = 1.0 / (1.0 + np.exp(-eta))
    w = np.clip(p * (1.0 - p), 1e-8, None)
    cov = np.linalg.pinv((x.T * w) @ x)
    se = np.sqrt(np.maximum(np.diag(cov), 0))

    rows = []
    for name, coef, stderr in zip(names, beta, se):
        zval = float(coef / stderr) if stderr else 0.0
        pval = math.erfc(abs(zval) / math.sqrt(2.0))
        rows.append(
            {
                "term": name,
                "beta": float(coef),
                "se": float(stderr),
                "z": zval,
                "p": pval,
                "or": _safe_exp(coef),
                "ci95_low": _safe_exp(coef - 1.96 * stderr),
                "ci95_high": _safe_exp(coef + 1.96 * stderr),
                "converged": converged,
                "numerical_boundary": "Large OR/CI values may indicate sparse data or separation." if abs(coef) > 20 or stderr > 20 else "",
            }
        )
    return rows


def _safe_exp(value):
    if value > 700:
        return "overflow_gt_1e304"
    if value < -700:
        return 0.0
    return float(math.exp(value))


def _zscore_vector(values):
    mu = mean(values)
    sd = _std(values)
    if sd == 0:
        return [0.0 for _ in values]
    return [(value - mu) / sd for value in values]


def _pooled_sd(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    var = ((len(a) - 1) * _std(a) ** 2 + (len(b) - 1) * _std(b) ** 2) / (len(a) + len(b) - 2)
    return math.sqrt(var)


def _odds_ratio(a, b, c, d):
    # Haldane-Anscombe correction.
    a2, b2, c2, d2 = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    orv = (a2 * d2) / (b2 * c2)
    se = math.sqrt(1/a2 + 1/b2 + 1/c2 + 1/d2)
    lo = math.exp(math.log(orv) - 1.96 * se)
    hi = math.exp(math.log(orv) + 1.96 * se)
    return {"or": round(orv, 6), "ci95_low": round(lo, 6), "ci95_high": round(hi, 6)}


def _binary_outcome(value):
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "dead", "death", "deceased", "event"}:
        return 1
    if v in {"0", "false", "no", "alive", "survived", "survivor", "none"}:
        return 0
    return None


def _safe_get(mapping, key):
    return mapping.get(key)


def _to_float(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except ValueError:
        return None


def _std(values):
    if len(values) <= 1:
        return 0.0
    mu = mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / (len(values) - 1))


def _quantile(values, q):
    vals = sorted(values)
    if not vals:
        return 0.0
    idx = (len(vals) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[int(idx)]
    return vals[lo] * (hi - idx) + vals[hi] * (idx - lo)


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path, report):
    lines = [
        "# PC11 Locked Validation Run",
        "",
        "Research-use-only validation output. This does not prove treatment efficacy, safety, clinical utility, or regulatory readiness.",
        "",
        f"Cohort: {report['cohort_id']}",
        f"Matched samples: {report['n_matched_samples']}",
        f"PC11 score computable: {report['verdict']['pc11_score_computable']}",
        "",
        "## Gene coverage",
        f"- Detected genes: {report['gene_coverage']['detected_gene_count']}",
        f"- Minimum required: {report['gene_coverage']['minimum_detected_genes_required']}",
        "",
        "## Score summary",
        f"- Median: {report['score_summary']['median']}",
        f"- SD: {report['score_summary']['sd']}",
        "",
    ]
    outcome = report.get("outcome_association")
    if outcome:
        lines.extend(
            [
                "## Outcome association",
                f"- Outcome column: {outcome.get('outcome_column')}",
                f"- Evaluable samples: {outcome.get('mortality_evaluable_n')}",
                f"- PC11-high events: {outcome.get('pc11_high_events')} / {outcome.get('pc11_high_n')}",
                f"- PC11-low events: {outcome.get('pc11_low_events')} / {outcome.get('pc11_low_n')}",
                f"- OR high vs low: {outcome.get('odds_ratio_high_vs_low', {}).get('or')}",
                "",
            ]
        )
    formal = report.get("formal_validation_stats")
    if formal and formal.get("model_1_death_pc11_z"):
        pc11 = next((row for row in formal["model_1_death_pc11_z"] if row.get("term") == "pc11_z"), None)
        if pc11:
            lines.extend(
                [
                    "## Formal validation stats",
                    f"- death ~ PC11_z OR: {_fmt_number(pc11.get('or'))}",
                    f"- death ~ PC11_z p: {_fmt_number(pc11.get('p'))}",
                    "",
                ]
            )
    endotype = report.get("endotype_structure_review")
    if endotype and endotype.get("eta_squared") is not None:
        lines.extend(
            [
                "## Endotype structure",
                f"- Endotype column: {endotype.get('endotype_class_column')}",
                f"- Eta squared: {endotype.get('eta_squared')}",
                f"- F statistic: {endotype.get('f_statistic')}",
                "",
            ]
        )
    conclusion = report.get("validation_conclusion", {})
    lines.extend(
        [
            "## Evidence grade",
            f"- PC11 computability: {conclusion.get('pc11_computability')}",
            f"- Gene coverage: {conclusion.get('gene_coverage')}",
            f"- External biology/endotype structure: {conclusion.get('external_biology_endotype_structure')}",
            f"- Mortality association: {conclusion.get('mortality_association')}",
            f"- Vasopressin-response replication: {conclusion.get('vasopressin_response_replication')}",
            f"- Drug claim: {conclusion.get('drug_claim')}",
            f"- Clinical use: {conclusion.get('clinical_use')}",
            f"- Regulatory readiness: {conclusion.get('regulatory_readiness')}",
            "",
            "## Cannot claim",
        ]
    )
    for item in CLAIM_BOUNDARY["not_allowed"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_conclusion_markdown(path, report):
    conclusion = report.get("validation_conclusion", {})
    coverage = report["gene_coverage"]
    outcome = report.get("outcome_association") or {}
    formal = report.get("formal_validation_stats") or {}
    endotype = report.get("endotype_structure_review") or {}
    pc11 = None
    if formal.get("model_1_death_pc11_z"):
        pc11 = next((row for row in formal["model_1_death_pc11_z"] if row.get("term") == "pc11_z"), None)

    lines = [
        f"# PC11 / VasoGate External Validation Conclusion — {report['cohort_id']}",
        "",
        "Research-use-only conclusion. This does not prove treatment efficacy, safety, clinical utility, bedside vasopressor selection, or regulatory readiness.",
        "",
        "## External computability",
        f"- Matched samples: {report['n_matched_samples']}",
        f"- PC11 genes requested: {coverage['positive_genes_requested'] + coverage['negative_genes_requested']}",
        f"- PC11 genes detected: {coverage['detected_gene_count']}",
        f"- Minimum required genes: {coverage['minimum_detected_genes_required']}",
        f"- Gene coverage gate: {conclusion.get('gene_coverage')}",
        "",
    ]
    if outcome:
        lines.extend(
            [
                "## Mortality association",
                f"- Evaluable samples: {outcome.get('mortality_evaluable_n')}",
                f"- PC11-high mortality: {outcome.get('pc11_high_events')} / {outcome.get('pc11_high_n')}",
                f"- PC11-low mortality: {outcome.get('pc11_low_events')} / {outcome.get('pc11_low_n')}",
                f"- Median-split OR high vs low: {outcome.get('odds_ratio_high_vs_low', {}).get('or')}",
            ]
        )
        if pc11:
            lines.extend([f"- Continuous PC11 OR: {_fmt_number(pc11.get('or'))}", f"- Continuous PC11 p: {_fmt_number(pc11.get('p'))}"])
        lines.append("")
    if endotype and endotype.get("eta_squared") is not None:
        lines.extend(
            [
                "## Endotype structure",
                f"- Eta squared: {endotype.get('eta_squared')}",
                f"- F statistic: {endotype.get('f_statistic')}",
                "",
            ]
        )
        for group in endotype.get("groups", []):
            lines.append(f"- {group['endotype_class']}: median PC11 = {group['median_pc11']}, n = {group['n']}")
        lines.append("")
    lines.extend(
        [
            "## Evidence grade",
            f"- PC11 computability: {conclusion.get('pc11_computability')}",
            f"- PC11 gene coverage: {conclusion.get('gene_coverage')}",
            f"- PC11 external biology/endotype structure: {conclusion.get('external_biology_endotype_structure')}",
            f"- PC11 mortality association: {conclusion.get('mortality_association')}",
            f"- PC11 vasopressin-response replication: {conclusion.get('vasopressin_response_replication')}",
            f"- Drug claim: {conclusion.get('drug_claim')}",
            f"- Clinical use claim: {conclusion.get('clinical_use')}",
            f"- Regulatory readiness: {conclusion.get('regulatory_readiness')}",
            "",
            "## Conclusion",
            conclusion.get("summary", ""),
            "",
            "No drug, safety, dosing, clinical treatment, bedside decision-support, or regulatory claim is supported.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt_number(value):
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return value
