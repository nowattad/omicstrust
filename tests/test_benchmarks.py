from __future__ import annotations

from omicstrust.benchmarks.benchmark_runner import run_synthetic_benchmark
from omicstrust.benchmarks.synthetic_generator import generate_synthetic_singlecell


def test_synthetic_generator_shapes():
    data = generate_synthetic_singlecell(n_cells=12, n_genes=9, rank=3)
    assert data["X"].shape == (12, 9)
    assert data["obs"].shape[0] == 12
    assert data["var"].shape[0] == 9


def test_benchmark_writes_outputs(tmp_path):
    out = tmp_path / "benchmark"
    run_synthetic_benchmark(out)
    assert (out / "benchmark_report.csv").exists()
    assert (out / "failure_heatmap.png").exists()
