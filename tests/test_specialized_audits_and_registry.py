from __future__ import annotations

import numpy as np
import pandas as pd
from typer.testing import CliRunner

from omicstrust.audit import run_audit
from omicstrust.cli.main import app
from omicstrust.perturb.audit import compute_perturb_report
from omicstrust.spatial.audit import compute_spatial_report
from omicstrust.tracking.sqlite_registry import list_registered_runs, register_run
from tests.conftest import write_fast_config


def test_spatial_and_perturb_reports_direct():
    obs = pd.DataFrame(
        {
            "array_row": [0, 0, 1, 1],
            "array_col": [0, 1, 0, 1],
            "in_tissue": [1, 1, 0, 1],
            "guide": ["g1", "g1", "g2", "g2"],
        }
    )
    scores = np.array([[0.0, 1.0], [0.2, 0.9], [1.0, 0.1], [1.1, 0.0]])
    spatial = compute_spatial_report(obs, scores)
    perturb = compute_perturb_report(obs, scores)
    assert spatial["available"] is True
    assert spatial["coordinate_summary"]["n_valid_coordinates"] == 4
    assert perturb["available"] is True
    assert perturb["perturbation_key"] == "guide"


def test_audit_writes_specialized_reports_and_registry(tmp_path):
    import anndata as ad

    X = np.abs(np.random.default_rng(0).normal(size=(40, 30))).astype("float32")
    obs = pd.DataFrame(
        {
            "array_row": np.repeat(np.arange(8), 5),
            "array_col": np.tile(np.arange(5), 8),
            "in_tissue": [1] * 40,
            "guide": ["ctrl"] * 20 + ["target"] * 20,
        },
        index=[f"cell_{i}" for i in range(40)],
    )
    var = pd.DataFrame(index=[f"gene_{i}" for i in range(30)])
    h5ad = tmp_path / "spatial_perturb.h5ad"
    ad.AnnData(X=X, obs=obs, var=var).write_h5ad(h5ad)
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "audit"
    run_audit(h5ad, output=out, config_path=cfg)

    assert (out / "spatial_report.json").exists()
    assert (out / "perturb_report.json").exists()
    assert (out / "figures" / "spatial_layout.png").exists()
    assert (out / "figures" / "perturbation_groups.png").exists()

    db = tmp_path / "registry.sqlite"
    record = register_run(out, db)
    runs = list_registered_runs(db)
    assert runs[0]["run_id"] == record["run_id"]


def test_cli_register_and_runs(tmp_path):
    import anndata as ad

    X = np.abs(np.random.default_rng(1).normal(size=(30, 20))).astype("float32")
    h5ad = tmp_path / "tiny.h5ad"
    ad.AnnData(X=X).write_h5ad(h5ad)
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "audit"
    run_audit(h5ad, output=out, config_path=cfg)
    db = tmp_path / "registry.sqlite"
    runner = CliRunner()
    register_result = runner.invoke(app, ["register", str(out), "--db", str(db)])
    assert register_result.exit_code == 0, register_result.output
    runs_result = runner.invoke(app, ["runs", "--db", str(db)])
    assert runs_result.exit_code == 0, runs_result.output
    assert "trust_score" in runs_result.output
