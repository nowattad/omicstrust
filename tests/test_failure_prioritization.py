from __future__ import annotations

from omicstrust.reports.executive_summary import build_summary
from omicstrust.risk.failure_modes import build_failure_report, choose_main_failure


def test_batch_dominated_signal_is_primary_failure_over_warnings():
    metadata = {
        "batch_key": "tech",
        "donor_key": None,
        "label_key": "celltype",
        "obs_columns": ["tech", "celltype", "size_factors"],
        "missing_metadata_warnings": ["missing_donor_metadata"],
        "interpretation_limited": True,
    }
    failure_report = build_failure_report(
        qc_report={
            "qc_status": "warning",
            "warnings": ["large_matrix_detected"],
            "matrix_shape": [16_382, 19_093],
            "identifier_warnings": [],
        },
        signal_report={"signal_score": 0.6},
        null_report={
            "n_components_above_null": 17,
            "calibration_status": "limited_permutation_resolution",
            "calibration_diagnostics": {
                "n_permutations": 20,
                "p_value_resolution": 1 / 21,
                "fraction_at_resolution_floor": 0.85,
            },
        },
        batch_risk_report={
            "max_batch_r2": 0.79,
            "overall_risk": "high",
            "metadata_assessment": metadata,
            "components": [
                {
                    "component": 1,
                    "risk": "high",
                    "max_batch_r2": 0.79,
                    "label_r2": 0.22,
                }
            ],
        },
        stability_report={"mean_subspace_similarity": 0.98},
        metadata_assessment=metadata,
    )

    assert failure_report["failures"][0]["failure_type"] == "batch_dominated_signal"
    assert failure_report["highest_severity"] == "high"

    summary = build_summary(
        qc_report={"qc_status": "warning"},
        signal_report={"signal_score": 0.6},
        null_report={"n_components_above_null": 17},
        batch_risk_report={"overall_risk": "high", "max_batch_r2": 0.79, "donor_risk": "unknown", "label_assessment": "assessable"},
        stability_report={"stability_status": "high"},
        trust_report={"trust_level": "unsafe", "safe_to_interpret": False, "safe_to_interpret_biologically": False},
        failure_report=failure_report,
    )

    assert summary["main_failure"] == "batch_dominated_signal"
    assert "Do not interpret" in summary["recommendation"]


def test_all_core_metadata_missing_beats_limited_null_resolution():
    metadata = {
        "batch_key": None,
        "donor_key": None,
        "label_key": None,
        "obs_columns": ["in_tissue", "array_row", "array_col"],
        "missing_metadata_warnings": [
            "missing_batch_metadata",
            "missing_donor_metadata",
            "missing_label_metadata",
        ],
        "interpretation_limited": True,
        "all_core_metadata_missing": True,
    }
    failure_report = build_failure_report(
        qc_report={
            "qc_status": "pass",
            "warnings": [],
            "identifier_warnings": ["duplicate_var_names_warning"],
            "duplicated_cell_ids": 0,
            "duplicated_gene_ids": 2,
        },
        signal_report={"signal_score": 0.7},
        null_report={
            "n_components_above_null": 4,
            "calibration_status": "limited_permutation_resolution",
            "calibration_diagnostics": {
                "n_permutations": 20,
                "p_value_resolution": 1 / 21,
                "fraction_at_resolution_floor": 0.8,
            },
        },
        batch_risk_report={
            "max_batch_r2": 0.0,
            "overall_risk": "unknown",
            "metadata_assessment": metadata,
            "components": [{"component": 1, "risk": "unknown"}],
        },
        stability_report={"mean_subspace_similarity": 0.98},
        metadata_assessment=metadata,
    )

    main = choose_main_failure(failure_report["failures"])

    assert main is not None
    assert main["failure_type"] == "metadata_insufficient_for_interpretation"
    assert failure_report["failures"][0]["failure_type"] == "metadata_insufficient_for_interpretation"
