from __future__ import annotations

from typing import Any

from omicstrust.risk.failure_modes import choose_main_failure


def build_summary(
    *,
    qc_report: dict[str, Any],
    signal_report: dict[str, Any],
    null_report: dict[str, Any],
    batch_risk_report: dict[str, Any],
    stability_report: dict[str, Any],
    trust_report: dict[str, Any],
    failure_report: dict[str, Any],
) -> dict[str, Any]:
    signal_detected = int(null_report.get("n_components_above_null", 0) or 0) > 0
    high_batch = batch_risk_report.get("overall_risk") != "unknown" and float(batch_risk_report.get("max_batch_r2", 0.0) or 0.0) >= 0.5
    primary_failure = choose_main_failure(list(failure_report.get("failures", [])))
    main_failure = primary_failure.get("failure_type") if primary_failure else None
    return {
        "title": "OmicsTrust Audit Summary",
        "data_qc": qc_report.get("qc_status"),
        "structural_signal": "detected" if signal_detected else "not_detected_above_null",
        "empirical_null": "passed" if signal_detected else "not_passed",
        "batch_risk": "high" if high_batch else batch_risk_report.get("overall_risk", "low"),
        "donor_risk": batch_risk_report.get("donor_risk", "unknown"),
        "label_assessment": batch_risk_report.get("label_assessment", "not_assessable"),
        "stability": stability_report.get("stability_status"),
        "trust_level": trust_report.get("trust_level"),
        "safe_to_interpret_biologically": "yes" if trust_report.get("safe_to_interpret_biologically") else "no",
        "safe_to_interpret": "yes" if trust_report.get("safe_to_interpret") else "no",
        "main_failure": main_failure,
        "recommendation": _recommendation(primary_failure, high_batch),
    }


def _recommendation(primary_failure: dict[str, Any] | None, high_batch: bool) -> str:
    if primary_failure:
        return str(primary_failure.get("recommendation"))
    if high_batch:
        return "Do not interpret batch-associated components biologically without residualized sensitivity analysis."
    return "Treat structural findings as statistically supported audit evidence, then validate biological interpretation externally."
