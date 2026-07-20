from __future__ import annotations

from typer.testing import CliRunner

from omicstrust.cli.main import app
from omicstrust.datasets.discovery import discover_datasets
from omicstrust.suite.runner import run_audit_suite
from omicstrust.workflows.doctor import run_doctor
from tests.conftest import synthetic_h5ad, write_fast_config


def test_discover_datasets_inspects_h5ad(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    records = discover_datasets([tmp_path])
    assert len(records) == 1
    assert records[0].path == str(h5ad)
    assert records[0].status == "ok"
    assert records[0].suggested_keys["batch_key"] == "batch"


def test_doctor_reports_environment_and_dataset(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    report = run_doctor(project_root=tmp_path, data_paths=[h5ad], output=tmp_path / "doctor")
    assert report["n_failed"] == 0
    assert (tmp_path / "doctor" / "doctor_report.json").exists()


def test_audit_suite_runs_multiple_inputs(tmp_path):
    first = synthetic_h5ad(tmp_path / "first.h5ad")
    second = synthetic_h5ad(tmp_path / "second.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "suite"
    report = run_audit_suite([first, second], output=out, config_path=cfg)
    assert report["n_ok"] == 2
    assert (out / "suite_report.csv").exists()
    assert (out / "runs" / "first" / "summary.json").exists()


def test_cli_discover_doctor_and_suite(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    runner = CliRunner()
    discover_result = runner.invoke(app, ["discover", "--root", str(tmp_path), "--output", str(tmp_path / "discovery")])
    assert discover_result.exit_code == 0, discover_result.output
    assert (tmp_path / "discovery" / "dataset_discovery.json").exists()

    doctor_result = runner.invoke(app, ["doctor", "--data", str(h5ad), "--output", str(tmp_path / "doctor")])
    assert doctor_result.exit_code == 0, doctor_result.output
    assert (tmp_path / "doctor" / "doctor_report.json").exists()

    suite_result = runner.invoke(app, ["suite", str(h5ad), "--output", str(tmp_path / "suite_cli"), "--config", str(cfg)])
    assert suite_result.exit_code == 0, suite_result.output
    assert (tmp_path / "suite_cli" / "suite_report.json").exists()
