from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

FAILURE_PRIORITY = {
    "batch_dominated_signal": 100,
    "donor_dominated_signal": 95,
    "technical_covariate_dominance": 90,
    "metadata_insufficient_for_interpretation": 85,
    "batch_risk_not_assessable": 82,
    "missing_metadata_warning": 80,
    "null_miscalibration": 70,
    "limited_null_resolution": 60,
    "insufficient_null_permutations": 58,
    "unstable_subspace": 55,
    "unstable_rank": 50,
    "duplicate_var_names_warning": 45,
    "duplicate_obs_names_warning": 45,
    "baseline_outperforms_primary_method": 40,
    "high_sparsity_warning": 35,
    "large_matrix_processing_warning": 20,
    "no_signal_above_null": 15,
}


def build_failure_report(
    *,
    qc_report: dict[str, Any],
    signal_report: dict[str, Any],
    null_report: dict[str, Any],
    batch_risk_report: dict[str, Any],
    stability_report: dict[str, Any],
    metadata_assessment: dict[str, Any] | None = None,
    benchmark_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    metadata_assessment = metadata_assessment or batch_risk_report.get("metadata_assessment", {})
    if metadata_assessment.get("all_core_metadata_missing"):
        failures.append(_failure(
            "metadata_insufficient_for_interpretation",
            "high",
            {
                "all_core_metadata_missing": True,
                "batch_key": metadata_assessment.get("batch_key"),
                "donor_key": metadata_assessment.get("donor_key"),
                "label_key": metadata_assessment.get("label_key"),
                "obs_columns": metadata_assessment.get("obs_columns", []),
                "missing": metadata_assessment.get("missing_metadata_warnings", []),
            },
            "Structural signal is present and reproducible, but no batch, donor, or biological label metadata are available, so biological interpretation cannot be certified.",
            "Add batch/sample/donor/condition/cell-type metadata or restrict the report to technical structural auditing only.",
        ))
    elif metadata_assessment.get("missing_metadata_warnings"):
        failures.append(_failure(
            "missing_metadata_warning",
            "medium",
            {
                "batch_key": metadata_assessment.get("batch_key"),
                "donor_key": metadata_assessment.get("donor_key"),
                "label_key": metadata_assessment.get("label_key"),
                "obs_columns": metadata_assessment.get("obs_columns", []),
                "missing": metadata_assessment.get("missing_metadata_warnings", []),
            },
            "Structural signal was detected, but batch, donor, and/or biological label metadata were not available, so biological interpretability and confounding risk cannot be fully assessed.",
            "Provide batch, donor, sample, condition, or cell-type metadata before claiming biological interpretability.",
        ))

    if qc_report.get("identifier_warnings"):
        failures.append(_failure(
            "duplicate_var_names_warning" if "duplicate_var_names_warning" in qc_report.get("identifier_warnings", []) else "duplicate_obs_names_warning",
            "medium",
            {
                "duplicated_cell_ids": qc_report.get("duplicated_cell_ids"),
                "duplicated_gene_ids": qc_report.get("duplicated_gene_ids"),
                "identifier_warnings": qc_report.get("identifier_warnings", []),
            },
            "Observation or feature identifiers are duplicated, which can weaken feature-level interpretation, loadings, and top-gene reporting.",
            "Make observation and feature names unique before using feature-level biological interpretations.",
        ))

    if qc_report.get("qc_status") == "fail":
        failures.append(_failure(
            "technical_covariate_dominance",
            "high",
            {"qc_status": qc_report.get("qc_status"), "warnings": qc_report.get("warnings", [])},
            "The dataset has technical QC failures that can invalidate downstream interpretation.",
            "Fix matrix quality issues before interpreting structural signal.",
        ))
    elif qc_report.get("warnings"):
        large_warnings = [w for w in qc_report.get("warnings", []) if str(w).startswith("large_matrix")]
        other_warnings = [w for w in qc_report.get("warnings", []) if not str(w).startswith("large_matrix")]
        if large_warnings:
            failures.append(_failure(
                "large_matrix_processing_warning",
                "low",
                {"warnings": large_warnings, "matrix_shape": qc_report.get("matrix_shape")},
                "The input matrix is large enough that dense preprocessing steps can become a memory risk.",
                "Use sparse-aware or chunked preprocessing, randomized solvers, and avoid dense centering unless the feature space is reduced.",
            ))
        if other_warnings:
            failure_type = "missing_metadata_warning" if any("key" in str(w) for w in other_warnings) else "high_sparsity_warning"
            failures.append(_failure(
                failure_type,
                "medium",
                {"warnings": other_warnings},
                "The audit found metadata or sparsity warnings that limit interpretability.",
                "Review metadata completeness and sparsity before biological interpretation.",
            ))

    above_null = int(null_report.get("n_components_above_null", 0) or 0)
    if above_null == 0:
        failures.append(_failure(
            "no_signal_above_null",
            "high",
            {"n_components_above_null": above_null},
            "No fitted spectral component was statistically detectable above the empirical null.",
            "Treat downstream biological interpretation as unsupported; increase sample size or revisit preprocessing.",
        ))

    for component in batch_risk_report.get("components", []):
        if component.get("risk") == "high":
            failures.append(_failure(
                "batch_dominated_signal",
                "high",
                {
                    "component": component.get("component"),
                    "max_batch_r2": component.get("max_batch_r2"),
                    "label_r2": component.get("label_r2"),
                },
                "The strongest detected structure is more associated with batch/donor than with the biological label.",
                "Do not interpret the affected component biologically. Use within-batch nulls and residualized sensitivity analyses.",
            ))
            break

    mean_similarity = float(stability_report.get("mean_subspace_similarity", 1.0) or 0.0)
    if mean_similarity < 0.5:
        failures.append(_failure(
            "unstable_subspace",
            "high",
            {"mean_subspace_similarity": mean_similarity},
            "The fitted subspace changed substantially across bootstrap resamples.",
            "Increase sample size, reduce feature noise, or report the result as unstable.",
        ))
    elif mean_similarity < 0.7:
        failures.append(_failure(
            "unstable_subspace",
            "medium",
            {"mean_subspace_similarity": mean_similarity},
            "The fitted subspace has only moderate bootstrap stability.",
            "Use cautious interpretation and compare against baseline methods.",
        ))

    calibration_status = null_report.get("calibration_status")
    if calibration_status in {"insufficient_permutations", "limited_permutation_resolution", "anti-conservative"}:
        diagnostics = null_report.get("calibration_diagnostics", {})
        if calibration_status == "anti-conservative":
            failure_type = "null_miscalibration"
            interpretation = "The empirical null appears anti-conservative at the current threshold."
            recommendation = "Increase permutations and inspect null calibration before interpretation."
        elif calibration_status == "limited_permutation_resolution":
            failure_type = "limited_null_resolution"
            interpretation = (
                "The empirical null detected signal, but many p-values sit at the permutation resolution floor, "
                "so calibration precision is limited."
            )
            recommendation = "Increase permutations before claiming precise p-values or calibrated thresholds."
        else:
            failure_type = "insufficient_null_permutations"
            interpretation = "The empirical null has too few permutations to support confident thresholding."
            recommendation = "Increase permutations and inspect null calibration before interpretation."
        failures.append(_failure(
            failure_type,
            "medium",
            {
                "calibration_status": calibration_status,
                "n_permutations": diagnostics.get("n_permutations", null_report.get("n_permutations")),
                "p_value_resolution": diagnostics.get("p_value_resolution"),
                "fraction_at_resolution_floor": diagnostics.get("fraction_at_resolution_floor"),
            },
            interpretation,
            recommendation,
        ))

    benchmark_rows = benchmark_rows or []
    primary_signal = float(signal_report.get("signal_score", 0.0) or 0.0)
    for row in benchmark_rows:
        if row.get("method") != "SSI" and float(row.get("signal_score", 0.0) or 0.0) > primary_signal + 0.2:
            failures.append(_failure(
                "baseline_outperforms_primary_method",
                "medium",
                {"baseline": row.get("method"), "baseline_signal_score": row.get("signal_score"), "ssi_signal_score": primary_signal},
                "A baseline method produced a stronger structural summary than the primary SSI run.",
                "Compare component associations and stability before prioritizing SSI-derived interpretation.",
            ))
            break

    failures = _prioritize_failures(failures)
    return {
        "failures": failures,
        "n_failures": len(failures),
        "highest_severity": _highest_severity(failures),
        "safe_to_interpret": not any(f["severity"] == "high" for f in failures) and not metadata_assessment.get("interpretation_limited", False),
    }


def _failure(failure_type: str, severity: str, evidence: dict[str, Any], interpretation: str, recommendation: str) -> dict[str, Any]:
    return {
        "failure_type": failure_type,
        "severity": severity,
        "evidence": evidence,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }


def _highest_severity(failures: list[dict[str, Any]]) -> str:
    highest = "none"
    for failure in failures:
        if SEVERITY_RANK.get(str(failure.get("severity")), 0) > SEVERITY_RANK.get(highest, 0):
            highest = str(failure.get("severity"))
    return highest


def choose_main_failure(failures: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not failures:
        return None
    return max(
        failures,
        key=lambda failure: (
            SEVERITY_RANK.get(str(failure.get("severity")), 0),
            FAILURE_PRIORITY.get(str(failure.get("failure_type")), 0),
        ),
    )


def _prioritize_failures(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        failures,
        key=lambda failure: (
            -SEVERITY_RANK.get(str(failure.get("severity")), 0),
            -FAILURE_PRIORITY.get(str(failure.get("failure_type")), 0),
        ),
    )
