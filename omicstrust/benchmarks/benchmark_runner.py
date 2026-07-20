from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import tempfile

import numpy as np
import pandas as pd
import yaml

from omicstrust.benchmarks.metrics import subspace_alignment
from omicstrust.benchmarks.synthetic_generator import generate_synthetic_singlecell
from omicstrust.signal.ssi_engine import SSIEngine
from omicstrust.utils.memory import peak_memory_mb
from omicstrust.utils.serialization import write_json
from omicstrust.utils.timing import now, runtime_seconds


def run_synthetic_benchmark(output: str | Path, config_path: str | Path | None = None) -> dict[str, Any]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    config = _load_benchmark_config(config_path)
    rows = []
    snr_values = config.get("sweeps", {}).get("snr", [0.25, 0.5, 1.0, 2.0])
    for snr in snr_values:
        start = now()
        data = generate_synthetic_singlecell(
            n_cells=int(config.get("n_cells", 300)),
            n_genes=int(config.get("n_genes", 120)),
            rank=int(config.get("rank", 4)),
            snr=float(snr),
            dropout_rate=float(config.get("dropout_rate", 0.2)),
            batch_strength=float(config.get("batch_strength", 0.5)),
            random_state=int(config.get("random_state", 42)),
        )
        engine = SSIEngine(n_components=int(config.get("n_components", 6)), random_state=int(config.get("random_state", 42))).fit(data["X"])
        estimated_feature_space = engine.components().T
        true_feature_space = np.asarray(data["true_loadings"]).T[:, : estimated_feature_space.shape[1]]
        rows.append(
            {
                "benchmark": "snr_sweep",
                "snr": float(snr),
                "method": "SSI",
                "subspace_alignment": subspace_alignment(true_feature_space, estimated_feature_space),
                "signal_score": float(engine.diagnostics().get("signal_score", 0.0)),
                "selected_rank": int(engine.diagnostics().get("selected_rank", 0)),
                "runtime_seconds": runtime_seconds(start),
                "memory_mb": peak_memory_mb(),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "benchmark_report.csv", index=False)
    frame[["snr", "runtime_seconds"]].to_csv(output / "runtime.csv", index=False)
    frame[["snr", "memory_mb"]].to_csv(output / "memory.csv", index=False)
    write_json(output / "benchmark_summary.json", {"n_runs": len(rows), "best_alignment": float(frame["subspace_alignment"].max())})
    _write_benchmark_figures(output, frame)
    return {"rows": rows, "output": str(output)}


def _load_benchmark_config(config_path: str | Path | None) -> dict[str, Any]:
    default = {
        "n_cells": 300,
        "n_genes": 120,
        "rank": 4,
        "dropout_rate": 0.2,
        "batch_strength": 0.5,
        "n_components": 6,
        "random_state": 42,
        "sweeps": {"snr": [0.25, 0.5, 1.0, 2.0]},
    }
    if not config_path or not Path(config_path).exists():
        return default
    with Path(config_path).open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    default.update(loaded)
    return default


def _write_benchmark_figures(output: Path, frame: pd.DataFrame) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "omicstrust-matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(5, 3.5))
    plt.plot(frame["snr"], frame["subspace_alignment"], marker="o")
    plt.xlabel("SNR")
    plt.ylabel("subspace alignment")
    plt.ylim(0, 1)
    plt.title("SNR vs Alignment")
    plt.tight_layout()
    plt.savefig(output / "snr_vs_alignment.png", dpi=150)
    plt.close()

    plt.figure(figsize=(5, 3.5))
    plt.plot(frame["snr"], frame["signal_score"], marker="o")
    plt.xlabel("SNR")
    plt.ylabel("signal score")
    plt.ylim(0, 1)
    plt.title("Dropout vs Performance Proxy")
    plt.tight_layout()
    plt.savefig(output / "dropout_vs_performance.png", dpi=150)
    plt.close()

    plt.figure(figsize=(5, 3.5))
    plt.plot(frame["snr"], np.maximum(0, 1 - frame["subspace_alignment"]), marker="o")
    plt.xlabel("SNR")
    plt.ylabel("FPR proxy")
    plt.title("Batch Strength vs FPR Proxy")
    plt.tight_layout()
    plt.savefig(output / "batch_strength_vs_fpr.png", dpi=150)
    plt.close()

    plt.figure(figsize=(5, 3.5))
    values = np.asarray(1 - frame["subspace_alignment"])[None, :]
    plt.imshow(values, aspect="auto", cmap="Reds", vmin=0, vmax=1)
    plt.yticks([])
    plt.xticks(range(len(frame)), [str(v) for v in frame["snr"]])
    plt.xlabel("SNR")
    plt.colorbar(label="failure proxy")
    plt.title("Failure Heatmap")
    plt.tight_layout()
    plt.savefig(output / "failure_heatmap.png", dpi=150)
    plt.close()
