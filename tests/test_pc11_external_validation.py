from __future__ import annotations

import json

from typer.testing import CliRunner

from omicstrust.cli.main import app
from omicstrust.workflows.pc11_external_validation import run_pc11_external_validation_plan


def _write_discovery_summary(path):
    payload = {
        "axis_signature": {
            "axis_name": "VANISH PC11 / VasoGate Vasopressin Response Axis",
            "genes": ["PDIA6", "LILRB1", "MX1", "OAS2", "OAS3", "CCR2", "PSMB8"],
            "up_genes": ["PDIA6", "LILRB1", "CCR2"],
            "down_genes": ["MX1", "OAS2", "OAS3", "PSMB8"],
            "pathways": ["septic shock", "interferon", "myeloid", "ER stress"],
            "phenotype": "PC11 candidate vasopressin-response axis in septic shock",
            "disease_context": "VANISH septic shock whole-blood transcriptomic treatment-response discovery",
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_pc11_external_validation_package_outputs(tmp_path):
    report_path = _write_discovery_summary(tmp_path / "discovery_summary.json")
    out = tmp_path / "pc11_package"

    report = run_pc11_external_validation_plan(report_path, output=out)

    assert report["workflow"] == "pc11_external_validation_plan"
    assert report["status"] == "validation_package_generated"
    assert report["cohort_count"] >= 6
    assert report["query_count"] >= 12
    assert report["verdict"]["treatment_guidance_allowed"] is False
    assert report["verdict"]["clinical_use_allowed"] is False
    assert report["locked_axis_contract"]["scoring_rule"]["method"] == "directional_zscore_difference_v1"

    assert (out / "pc11_locked_axis_contract.json").exists()
    assert (out / "pc11_external_validation_protocol.json").exists()
    assert (out / "pc11_external_validation_cohorts.csv").exists()
    assert (out / "pc11_validation_queries.csv").exists()
    assert (out / "pc11_readiness_report.md").exists()

    forbidden = " ".join(report["claim_boundary"]["forbidden_claims"]).lower()
    assert "treatment efficacy proven" in forbidden
    assert "clinical treatment recommendation" in forbidden


def test_pc11_validate_plan_cli(tmp_path):
    report_dir = tmp_path / "pc11"
    report_dir.mkdir()
    _write_discovery_summary(report_dir / "discovery_summary.json")
    out = tmp_path / "cli_out"

    result = CliRunner().invoke(app, ["pc11-validate-plan", str(report_dir), "--output", str(out)])

    assert result.exit_code == 0, result.output
    assert "PC11 / VasoGate External Validation Package" in result.output
    assert "Treatment Guidance Allowed: False" in result.output
    assert (out / "pc11_external_validation_package.json").exists()
