from __future__ import annotations

from omicstrust.benchmarks.benchmark_runner import run_synthetic_benchmark


if __name__ == "__main__":
    run_synthetic_benchmark("results/benchmark_001", "configs/synthetic_benchmark.yaml")
