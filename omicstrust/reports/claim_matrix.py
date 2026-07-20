from __future__ import annotations

from typing import Any


def build_claim_matrix(context: dict[str, Any]) -> dict[str, Any]:
    summary = context.get("summary", {})
    trust = context.get("trust_report", {})
    metadata = context.get("metadata_assessment", {})
    failure = context.get("failure_report", {})
    null_report = context.get("null_report", {})
    batch = context.get("batch_risk_report", {})
    stability = context.get("stability_report", {})

    can_claim = [
        "The input dataset was loaded and audited with recorded provenance.",
        "The report separates structural signal, empirical-null support, confounding risk, and stability.",
    ]
    if summary.get("structural_signal") == "detected":
        can_claim.append("At least one structural component was detected above the configured empirical null.")
    if stability.get("stability_status") == "high":
        can_claim.append("The fitted subspace was stable under the configured bootstrap analysis.")
    if null_report.get("calibration_status") == "passed":
        can_claim.append("The empirical-null calibration did not raise a configured calibration warning.")
    if trust.get("safe_to_interpret_biologically"):
        can_claim.append("Biological interpretation is audit-supported under the supplied metadata and configuration.")

    cannot_claim = [
        "The audit does not prove biological truth or clinical utility.",
        "The audit does not replace external validation in an independent cohort.",
        "The audit is not a diagnostic, prognostic, or treatment-selection device.",
    ]
    if metadata.get("interpretation_limited"):
        cannot_claim.append("Biological interpretation cannot be certified because core metadata are incomplete.")
    if batch.get("overall_risk") in {"high", "unknown"}:
        cannot_claim.append("Low batch or donor confounding risk cannot be claimed from this run.")
    if failure.get("highest_severity") == "high":
        cannot_claim.append("High-trust biological interpretation cannot be claimed while high-severity failures are present.")
    if null_report.get("calibration_status") in {"limited_permutation_resolution", "insufficient_permutations"}:
        cannot_claim.append("Precise calibrated p-values cannot be claimed at the current permutation resolution.")

    next_actions = []
    if metadata.get("missing_metadata_warnings"):
        next_actions.append("Add batch, donor/sample, and biological label metadata, then rerun the audit.")
    if batch.get("overall_risk") == "high":
        next_actions.append("Run residualized and within-batch sensitivity analyses before interpretation.")
    if null_report.get("calibration_status") != "passed":
        next_actions.append("Increase null permutations for stronger calibration evidence.")
    if not next_actions:
        next_actions.append("Use the report as RUO audit evidence and validate any biological claim externally.")

    return {
        "can_claim": can_claim,
        "cannot_claim": cannot_claim,
        "next_actions": next_actions,
        "ruo_disclaimer": "Research Use Only. Not for diagnosis, prognosis, treatment selection, or regulated clinical decision-making.",
    }
