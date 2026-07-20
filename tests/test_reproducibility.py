from __future__ import annotations

from omicstrust.audit import run_audit
from omicstrust.workflows.reproduce import check_reproducibility
from tests.conftest import synthetic_h5ad, write_fast_config


def test_reproducibility_report(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "audit"
    run_audit(h5ad, batch_key="batch", label_key="signal_label", output=out, config_path=cfg)
    report = check_reproducibility(out)
    assert "exact_reproduction" in report
    assert (out / "reproducibility_report.json").exists()
