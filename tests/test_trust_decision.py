from __future__ import annotations

from omicstrust.trust import build_trust_report


def test_high_batch_dominance_is_never_upgraded_by_partial_metadata():
    report = build_trust_report(
        qc_report={"qc_status": "warning"},
        signal_report={"signal_score": 0.6, "eigenvalues": [3.0, 2.0, 1.0]},
        null_report={"n_components_above_null": 2},
        batch_risk_report={
            "max_batch_r2": 0.79,
            "overall_risk": "high",
            "metadata_assessment": {
                "interpretation_limited": True,
                "all_core_metadata_missing": False,
            },
        },
        stability_report={"mean_subspace_similarity": 0.98},
        reproducibility_report={"status": "reproduced"},
        failure_report={
            "highest_severity": "high",
            "safe_to_interpret": False,
            "failures": [
                {"failure_type": "batch_dominated_signal", "severity": "high"},
                {"failure_type": "missing_metadata_warning", "severity": "medium"},
            ],
        },
    )

    assert report["trust_level"] == "unsafe"
    assert report["final_decision"] == "unsafe_to_interpret_batch_dominated"
    assert report["safe_to_interpret"] is False
