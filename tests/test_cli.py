from __future__ import annotations

from typer.testing import CliRunner

from omicstrust.cli.main import app
from omicstrust.cli.inspect import suggest_metadata_keys
from omicstrust.cli.validate import _large_matrix_warnings
from tests.conftest import synthetic_h5ad, write_fast_config


def test_cli_audit_runs(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    cfg = write_fast_config(tmp_path / "config.yaml")
    out = tmp_path / "cli_audit"
    result = CliRunner().invoke(app, ["audit", str(h5ad), "--batch-key", "batch", "--label-key", "signal_label", "--output", str(out), "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert (out / "trust_report.json").exists()


def test_cli_missing_file_is_readable_error(tmp_path):
    missing = tmp_path / "missing.h5ad"
    result = CliRunner().invoke(app, ["validate", str(missing), "--batch-key", "batch"])
    assert result.exit_code == 1
    assert "Input file not found" in result.output
    assert "Traceback" not in result.output


def test_cli_inspect_lists_columns(tmp_path):
    h5ad = synthetic_h5ad(tmp_path / "synthetic.h5ad")
    result = CliRunner().invoke(app, ["inspect", str(h5ad)])
    assert result.exit_code == 0, result.output
    assert "obs_columns" in result.output
    assert "batch" in result.output


def test_inspect_suggests_scib_metadata_keys():
    suggested = suggest_metadata_keys(["tech", "celltype", "size_factors"])

    assert suggested["batch_key"] == "tech"
    assert suggested["label_key"] == "celltype"
    assert suggested["donor_key"] is None


def test_validate_warns_for_large_hvg_matrix():
    warnings = _large_matrix_warnings(
        (16_382, 19_093),
        {"hvg_selection": True, "scale": False},
    )

    assert "large_matrix_detected" in warnings
    assert "large_matrix_hvg_requires_sparse_or_chunked_variance" in warnings
    assert "large_matrix_scale_may_require_dense_memory" not in warnings


def test_moleculetrust_is_not_part_of_the_omicstrust_cli():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "molecule-trust" not in result.output
