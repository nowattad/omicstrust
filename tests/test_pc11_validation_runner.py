from __future__ import annotations

import csv
import json

from typer.testing import CliRunner

from omicstrust.cli.main import app
from omicstrust.workflows.pc11_validation_runner import run_pc11_validation


def _write_contract(path):
    payload = {
        "contract_id": "PC11_TEST",
        "axis_name": "PC11 test",
        "positive_direction_genes": ["PDIA6", "LILRB1"],
        "negative_direction_genes": ["MX1", "OAS2"],
        "scoring_rule": {
            "method": "directional_zscore_difference_v1",
            "minimum_detected_genes_required": 4,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


def _fixtures(tmp_path):
    contract = _write_contract(tmp_path / "contract.json")
    expr = []
    meta = []
    for i in range(20):
        sid = f"S{i:02d}"
        high = i >= 10
        expr.append({
            "sample_id": sid,
            "PDIA6": 10 + i if high else 2 + i * 0.1,
            "LILRB1": 9 + i if high else 1 + i * 0.1,
            "MX1": 1 + i * 0.1 if high else 10 + i,
            "OAS2": 2 + i * 0.1 if high else 9 + i,
        })
        meta.append({
            "sample_id": sid,
            "death28": "1" if high and i % 2 == 0 else "0",
            "vasopressor": "vasopressin" if i % 2 == 0 else "norepinephrine",
            "endotype_cohort": "validation" if i >= 10 else "discovery",
            "endotype_class": "Mars2" if high else "Mars4",
        })
    return contract, _write_csv(tmp_path / "expr.csv", expr), _write_csv(tmp_path / "meta.csv", meta)


def test_pc11_validation_runner_outputs(tmp_path):
    contract, expr, meta = _fixtures(tmp_path)
    out = tmp_path / "out"

    report = run_pc11_validation(
        contract,
        expr,
        meta,
        output=out,
        cohort_id="synthetic_external",
        outcome_column="death28",
        treatment_column="vasopressor",
    )

    assert report["workflow"] == "pc11_validation_runner"
    assert report["n_matched_samples"] == 20
    assert report["verdict"]["pc11_score_computable"] is True
    assert report["verdict"]["treatment_guidance_allowed"] is False
    assert report["outcome_association"]["pc11_high_n"] == 10
    assert report["treatment_interaction_descriptive"]["treatment_column"] == "vasopressor"
    assert report["formal_validation_stats"]["mortality_evaluable_n"] == 20
    assert report["endotype_structure_review"]["eta_squared"] > 0
    assert report["validation_conclusion"]["external_biology_endotype_structure"] in {"PASS", "WEAK"}

    assert (out / "pc11_sample_scores.csv").exists()
    assert (out / "pc11_gene_coverage.json").exists()
    assert (out / "pc11_formal_validation_stats.json").exists()
    assert (out / "pc11_endotype_structure_review.json").exists()
    assert (out / "PC11_EXTERNAL_VALIDATION_CONCLUSION.md").exists()
    assert (out / "pc11_validation_run_report.json").exists()


def test_pc11_run_validation_cli(tmp_path):
    contract, expr, meta = _fixtures(tmp_path)
    out = tmp_path / "cli"

    result = CliRunner().invoke(app, [
        "pc11-run-validation",
        "--contract", str(contract),
        "--expression", str(expr),
        "--metadata", str(meta),
        "--output", str(out),
        "--cohort-id", "synthetic_external",
        "--outcome-column", "death28",
        "--treatment-column", "vasopressor",
    ])

    assert result.exit_code == 0, result.output
    assert "PC11 Locked Validation Run" in result.output
    assert "Treatment Guidance Allowed: False" in result.output
    assert "External Biology/Endotype:" in result.output
    assert (out / "pc11_validation_run_report.json").exists()


def test_pc11_outcome_median_split_uses_only_outcome_evaluable_samples(tmp_path):
    contract = _write_contract(tmp_path / "contract.json")
    expr = [
        {"sample_id": "S0", "PDIA6": 10, "LILRB1": 10, "MX1": 1, "OAS2": 1},
        {"sample_id": "S1", "PDIA6": 9, "LILRB1": 9, "MX1": 2, "OAS2": 2},
        {"sample_id": "S2", "PDIA6": 2, "LILRB1": 2, "MX1": 9, "OAS2": 9},
        {"sample_id": "S3", "PDIA6": 1, "LILRB1": 1, "MX1": 10, "OAS2": 10},
    ]
    meta = [
        {"sample_id": "S0", "death28": ""},
        {"sample_id": "S1", "death28": "1"},
        {"sample_id": "S2", "death28": "0"},
        {"sample_id": "S3", "death28": ""},
    ]

    report = run_pc11_validation(
        contract,
        _write_csv(tmp_path / "expr.csv", expr),
        _write_csv(tmp_path / "meta.csv", meta),
        output=tmp_path / "out",
        outcome_column="death28",
    )

    assert report["outcome_association"]["mortality_evaluable_n"] == 2
    assert report["outcome_association"]["pc11_high_n"] == 1
    assert report["outcome_association"]["pc11_low_n"] == 1
