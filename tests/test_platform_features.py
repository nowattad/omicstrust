from __future__ import annotations

from fastapi.testclient import TestClient

from omicstrust.api.jobs import JobStore
from omicstrust.api.server import create_app
from omicstrust.case_studies.registry import get_case_study, list_case_studies, write_case_study_docs, write_case_study_json
from omicstrust.workflows.locked_validation import lock_axis_from_run, validate_locked_axis
from omicstrust.audit import run_audit
from omicstrust.utils.serialization import read_json
from tests.conftest import synthetic_h5ad, write_fast_config


def test_api_runs_path_audit(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    client = TestClient(create_app(results_root=tmp_path / "platform"))

    response = client.post(
        "/api/audits",
        json={
            "data_path": str(h5ad),
            "config_path": str(cfg),
            "batch_key": "batch",
            "label_key": "signal_label",
            "background": False,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    job_id = payload["job_id"]
    assert client.get(f"/api/jobs/{job_id}/summary.json").json()["structural_signal"] == "detected"
    assert client.get(f"/api/jobs/{job_id}/report.html").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/report.pdf").status_code == 200
    figure = client.get(f"/api/jobs/{job_id}/figures/qc_summary.png")
    assert figure.status_code == 200
    assert figure.content.startswith(b"\x89PNG")
    assert client.get(f"/api/jobs/{job_id}/figures/not-an-image.txt").status_code == 404

    store = JobStore(tmp_path / "platform")
    try:
        store.report_path(job_id, "../jobs.sqlite3")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Job artifact path traversal must be rejected.")


def test_api_token_protects_private_endpoints(tmp_path):
    client = TestClient(create_app(results_root=tmp_path / "platform", api_token="secret-token"))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["auth_required"] is True
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"X-OmicsTrust-Token": "secret-token"}).status_code == 200
    assert client.get("/api/jobs", headers={"Authorization": "Bearer secret-token"}).status_code == 200


def test_health_reports_gpt_privacy_boundary(tmp_path):
    client = TestClient(create_app(results_root=tmp_path / "platform"))

    payload = client.get("/health").json()

    assert payload["evidence_copilot"]["default_model"] == "gpt-5.6"
    assert payload["evidence_copilot"]["raw_expression_data_sent"] is False


def test_preserved_pc11_evidence_is_served(tmp_path):
    client = TestClient(create_app(results_root=tmp_path / "platform"))

    report = client.get("/api/case-studies/vanish_vasogate_pc11/report.pdf")
    summary = client.get("/api/case-studies/vanish_vasogate_pc11/discovery-summary.json")

    assert report.status_code == 200
    assert report.content.startswith(b"%PDF")
    assert summary.status_code == 200
    assert summary.json()["primary_result"]["top_candidate_axis"] == "PC11"
    assert summary.json()["clinical_use_allowed"] is False


def test_case_study_registry_is_focused_on_preserved_pc11_evidence():
    studies = list_case_studies()

    assert {study["id"] for study in studies} == {"vanish_vasogate_pc11"}
    assert "Research Use Only" in get_case_study("vanish_vasogate_pc11")["ruo_disclaimer"]


def test_case_studies_export_buyer_demo_package(tmp_path):
    md_path = write_case_study_docs(tmp_path)
    json_path = write_case_study_json(tmp_path)

    assert md_path.exists()
    assert json_path.exists()
    assert "VANISH / VasoGate PC11" in md_path.read_text(encoding="utf-8")
    payload = read_json(json_path)
    assert {study["id"] for study in payload["case_studies"]} == {"vanish_vasogate_pc11"}


def test_locked_axis_workflow_is_conservative(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    audit_dir = tmp_path / "audit"
    run_audit(h5ad, batch_key="batch", label_key="signal_label", output=audit_dir, config_path=cfg)

    contract = lock_axis_from_run(audit_dir, output=tmp_path / "locked", axis_name="synthetic_axis", component=1)
    validation = validate_locked_axis(
        tmp_path / "locked",
        h5ad,
        output=tmp_path / "validation",
        batch_key="batch",
        label_key="signal_label",
        config_path=cfg,
    )

    assert contract["axis_name"] == "synthetic_axis"
    assert validation["projection"]["projected"] is True
    assert validation["feature_coverage"] > 0
    assert validation["scores_file"] == "locked_axis_scores.csv"
    assert (tmp_path / "validation" / "locked_axis_scores.csv").exists()
    assert validation["decision"] in {
        "locked_validation_passed_for_ruo_followup",
        "audit_not_safe_to_interpret",
        "locked_validation_inconclusive",
    }
