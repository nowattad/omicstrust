from __future__ import annotations

import json

import numpy as np
import pandas as pd

from omicstrust.audit import run_audit
from tests.conftest import write_fast_config


def test_missing_core_metadata_blocks_high_trust_and_biological_safety(tmp_path):
    import anndata as ad

    X = np.abs(np.random.default_rng(7).normal(size=(50, 30))).astype("float32")
    obs = pd.DataFrame(
        {
            "in_tissue": [1] * 50,
            "array_row": np.repeat(np.arange(10), 5),
            "array_col": np.tile(np.arange(5), 10),
        },
        index=[f"spot_{i}" for i in range(50)],
    )
    var = pd.DataFrame(index=["gene_dup"] * 2 + [f"gene_{i}" for i in range(28)])
    h5ad = tmp_path / "metadata_limited.h5ad"
    ad.AnnData(X=X, obs=obs, var=var).write_h5ad(h5ad)
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "audit"

    run_audit(h5ad, output=out, config_path=cfg)

    summary = json.loads((out / "summary.json").read_text())
    trust = json.loads((out / "trust_report.json").read_text())
    batch = json.loads((out / "batch_risk_report.json").read_text())
    failure = json.loads((out / "failure_report.json").read_text())
    qc = json.loads((out / "qc_report.json").read_text())

    assert batch["overall_risk"] == "unknown"
    assert batch["batch_risk"] == "unknown"
    assert batch["donor_risk"] == "unknown"
    assert batch["label_assessment"] == "not_assessable"
    assert all(component["risk"] == "unknown" for component in batch["components"])
    assert batch["metadata_assessment"]["obs_columns"] == ["in_tissue", "array_row", "array_col"]
    assert summary["safe_to_interpret_biologically"] == "no"
    assert summary["trust_level"] == "insufficient_information"
    assert summary["main_failure"] == "metadata_insufficient_for_interpretation"
    assert trust["safe_to_interpret"] is False
    assert trust["trust_level"] == "insufficient_information"
    assert "duplicate_var_names_warning" in qc["identifier_warnings"]
    failure_types = {item["failure_type"] for item in failure["failures"]}
    assert "metadata_insufficient_for_interpretation" in failure_types
    assert "duplicate_var_names_warning" in failure_types
