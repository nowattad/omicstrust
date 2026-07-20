# Benchmark Protocol

The synthetic benchmark creates low-rank single-cell-like matrices with configurable signal-to-noise ratio, dropout, sparsity, batch effects, and confounded label/batch structure.

Default benchmark:

```bash
omicstrust benchmark --config configs/synthetic_benchmark.yaml --output results/benchmark_test
```

Outputs include `benchmark_report.csv`, `runtime.csv`, `memory.csv`, `failure_heatmap.png`, `snr_vs_alignment.png`, `dropout_vs_performance.png`, and `batch_strength_vs_fpr.png`.

Benchmark metrics are audit diagnostics. They should be reported with dataset size, random seed, and configuration.
