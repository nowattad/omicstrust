from __future__ import annotations

from typing import Any

import numpy as np


def build_trust_report(
    *,
    qc_report: dict[str, Any],
    signal_report: dict[str, Any],
    null_report: dict[str, Any],
    batch_risk_report: dict[str, Any],
    stability_report: dict[str, Any],
    reproducibility_report: dict[str, Any],
    failure_report: dict[str, Any],
) -> dict[str, Any]:
    qc_score = 1.0 if qc_report.get("qc_status") == "pass" else 0.65 if qc_report.get("qc_status") == "warning" else 0.2
    signal_score = float(signal_report.get("signal_score", 0.0) or 0.0)
    null_score = min(1.0, float(null_report.get("n_components_above_null", 0) or 0) / max(1, len(signal_report.get("eigenvalues", []))))
    metadata_assessment = batch_risk_report.get("metadata_assessment", {})
    metadata_insufficient = bool(metadata_assessment.get("interpretation_limited", False))
    max_batch = float(batch_risk_report.get("max_batch_r2", 0.0) or 0.0)
    batch_independence_score = 0.0 if batch_risk_report.get("overall_risk") == "unknown" else float(np.clip(1.0 - max_batch, 0.0, 1.0))
    stability_score = float(np.clip(stability_report.get("mean_subspace_similarity", 0.0) or 0.0, 0.0, 1.0))
    reproducibility_score = 1.0 if reproducibility_report.get("status") in {"captured", "reproduced"} else 0.5
    components = {
        "qc_score": qc_score,
        "signal_score": signal_score,
        "null_score": null_score,
        "batch_independence_score": batch_independence_score,
        "stability_score": stability_score,
        "reproducibility_score": reproducibility_score,
    }
    weights = {
        "qc_score": 0.15,
        "signal_score": 0.2,
        "null_score": 0.2,
        "batch_independence_score": 0.2,
        "stability_score": 0.15,
        "reproducibility_score": 0.1,
    }
    raw = sum(components[k] * weights[k] for k in weights)
    penalties: dict[str, float] = {}
    for failure in failure_report.get("failures", []):
        failure_type = str(failure.get("failure_type"))
        severity = str(failure.get("severity"))
        penalty = {"high": 0.25, "medium": 0.12, "low": 0.05}.get(severity, 0.0)
        penalties[failure_type] = max(penalties.get(failure_type, 0.0), penalty)
    score = float(np.clip(raw - sum(penalties.values()), 0.0, 1.0))
    if metadata_insufficient:
        score = min(score, 0.49 if metadata_assessment.get("all_core_metadata_missing") else 0.69)
    trust_score = int(round(score * 100))
    highest_severity = failure_report.get("highest_severity")
    if metadata_insufficient and metadata_assessment.get("all_core_metadata_missing"):
        trust_level = "insufficient_information"
        final_decision = "structural_signal_detected_but_metadata_insufficient"
    elif highest_severity == "high":
        trust_level = "unsafe"
        final_decision = "unsafe_to_interpret"
    elif metadata_insufficient:
        trust_level = "moderate" if trust_score >= 55 else "insufficient_information"
        final_decision = "metadata_limited_interpretation"
    elif trust_score >= 80:
        trust_level = "high"
        final_decision = "high_trust_statistical_structure"
    elif trust_score >= 55:
        trust_level = "moderate"
        final_decision = "moderate_trust_with_warnings" if penalties else "moderate_trust"
    elif trust_score >= 30:
        trust_level = "low"
        final_decision = "low_trust"
    else:
        trust_level = "insufficient_information"
        final_decision = "insufficient_information"
    if max_batch >= 0.5:
        if highest_severity == "high":
            trust_level = "unsafe"
            final_decision = "unsafe_to_interpret_batch_dominated"
        elif trust_level == "high":
            trust_level = "moderate"
            final_decision = "moderate_trust_with_batch_warning"
        else:
            final_decision = "batch_warning_limited_interpretation"
    return {
        "trust_score": trust_score,
        "trust_level": trust_level,
        "components": components,
        "penalties": penalties,
        "final_decision": final_decision,
        "safe_to_interpret": bool(failure_report.get("safe_to_interpret", False) and max_batch < 0.5 and not metadata_insufficient),
        "safe_to_interpret_biologically": bool(failure_report.get("safe_to_interpret", False) and max_batch < 0.5 and not metadata_insufficient),
        "metadata_assessment": metadata_assessment,
        "interpretation_note": "Trust score is an audit summary, not a probability of biological truth.",
    }
