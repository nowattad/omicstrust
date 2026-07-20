from __future__ import annotations

from omicstrust.audit import run_audit
from tests.conftest import synthetic_h5ad, write_fast_config


def test_audit_writes_reports(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "audit"
    run_audit(h5ad, batch_key="batch", label_key="signal_label", output=out, config_path=cfg)
    assert (out / "report.html").exists()
    assert (out / "report.pdf").exists()
    assert (out / "summary.json").exists()
    assert (out / "claim_matrix.json").exists()
    assert (out / "evidence_ledger.json").exists()
    assert (out / "artifacts" / "component_scores.csv").exists()
    assert (out / "artifacts" / "component_loadings.csv").exists()
    assert (out / "figures" / "qc_summary.png").exists()
