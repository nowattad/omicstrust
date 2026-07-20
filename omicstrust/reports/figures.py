from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import os
import tempfile


def generate_required_figures(
    output_dir: str | Path,
    *,
    qc_report: dict[str, Any],
    signal_report: dict[str, Any],
    null_report: dict[str, Any],
    batch_risk_report: dict[str, Any],
    stability_report: dict[str, Any],
    benchmark_rows: list[dict[str, Any]],
    failure_report: dict[str, Any],
    spatial_report: dict[str, Any] | None = None,
    perturb_report: dict[str, Any] | None = None,
    dpi: int = 150,
) -> list[dict[str, str]]:
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "omicstrust-matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = Path(output_dir) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    figures: list[dict[str, str]] = []

    def save(name: str, title: str):
        path = fig_dir / name
        plt.tight_layout()
        plt.savefig(path, dpi=dpi)
        plt.close()
        figures.append({"path": f"figures/{name}", "title": title})

    plt.figure(figsize=(5, 3.5))
    plt.bar(["zero", "nonzero"], [qc_report.get("zero_fraction", 0), qc_report.get("nonzero_fraction", 0)])
    plt.ylim(0, 1)
    plt.ylabel("fraction")
    plt.title("QC Matrix Sparsity")
    save("qc_summary.png", "QC summary")

    eigenvalues = np.asarray(signal_report.get("eigenvalues", []), dtype=float)
    thresholds = np.asarray(null_report.get("null_threshold", []), dtype=float)
    x = np.arange(1, max(len(eigenvalues), len(thresholds)) + 1)
    plt.figure(figsize=(5, 3.5))
    if eigenvalues.size:
        plt.plot(np.arange(1, eigenvalues.size + 1), eigenvalues, marker="o", label="observed")
    if thresholds.size:
        plt.plot(np.arange(1, thresholds.size + 1), thresholds, marker="s", label="null threshold")
    plt.xlabel("component")
    plt.ylabel("eigenvalue")
    plt.title("Spectrum vs Empirical Null")
    plt.legend()
    save("spectrum_vs_null.png", "Spectrum vs null")

    pvals = np.asarray(null_report.get("empirical_p_values", []), dtype=float)
    plt.figure(figsize=(5, 3.5))
    if pvals.size:
        plt.scatter(np.linspace(0, 1, pvals.size), np.sort(pvals), label="empirical p-values")
        plt.plot([0, 1], [0, 1], color="black", linewidth=1, label="reference")
    else:
        plt.text(0.5, 0.5, "No p-values", ha="center")
    plt.xlabel("expected quantile")
    plt.ylabel("observed p-value")
    plt.title("Null Calibration")
    plt.legend()
    save("null_calibration.png", "Null calibration")

    plt.figure(figsize=(5, 3.5))
    components = batch_risk_report.get("components", [])
    if batch_risk_report.get("overall_risk") == "unknown":
        plt.text(0.5, 0.5, "Batch/donor metadata unavailable\nrisk cannot be assessed", ha="center", va="center")
    elif components:
        plt.bar([str(c["component"]) for c in components], [_plot_value(c.get("max_batch_r2", 0)) for c in components])
    else:
        plt.text(0.5, 0.5, "No batch associations", ha="center")
    plt.ylim(0, 1)
    plt.xlabel("component")
    plt.ylabel("max batch/donor R2")
    plt.title("Batch Risk")
    save("batch_risk.png", "Batch risk")

    plt.figure(figsize=(5, 3.5))
    assoc = batch_risk_report.get("associations", [])
    tech = [r for r in assoc if r.get("covariate") in {"total_counts", "pct_counts_mt", "n_genes_by_counts"}]
    if tech:
        plt.bar([f"C{r['component']}:{r['covariate']}" for r in tech[:12]], [r.get("r2", 0) for r in tech[:12]])
        plt.xticks(rotation=45, ha="right")
    else:
        plt.text(0.5, 0.5, "No technical covariates available", ha="center")
    plt.ylim(0, 1)
    plt.ylabel("R2")
    plt.title("Technical Covariates")
    save("technical_covariates.png", "Technical covariates")

    plt.figure(figsize=(5, 3.5))
    sims = np.asarray(stability_report.get("subspace_similarity_values", []), dtype=float)
    if sims.size:
        plt.plot(np.arange(1, sims.size + 1), sims, marker="o")
    else:
        plt.text(0.5, 0.5, "No bootstrap data", ha="center")
    plt.ylim(0, 1)
    plt.xlabel("bootstrap")
    plt.ylabel("subspace similarity")
    plt.title("Bootstrap Stability")
    save("stability_bootstrap.png", "Bootstrap stability")

    plt.figure(figsize=(5, 3.5))
    if benchmark_rows:
        plt.bar([r["method"] for r in benchmark_rows], [float(r.get("signal_score") or 0) for r in benchmark_rows])
    else:
        plt.text(0.5, 0.5, "No baselines", ha="center")
    plt.ylim(0, 1)
    plt.ylabel("signal score")
    plt.title("Baseline Comparison")
    save("baseline_comparison.png", "Baseline comparison")

    plt.figure(figsize=(5, 3.5))
    failures = failure_report.get("failures", [])
    if failures:
        severity_map = {"low": 1, "medium": 2, "high": 3}
        values = [severity_map.get(f.get("severity"), 0) for f in failures]
        plt.imshow(np.asarray(values)[None, :], aspect="auto", vmin=0, vmax=3, cmap="Reds")
        plt.yticks([])
        plt.xticks(range(len(failures)), [f["failure_type"] for f in failures], rotation=45, ha="right")
        plt.colorbar(label="severity")
    else:
        plt.text(0.5, 0.5, "No detected failures", ha="center")
        plt.axis("off")
    plt.title("Failure Heatmap")
    save("failure_heatmap.png", "Failure heatmap")

    if spatial_report and spatial_report.get("available"):
        coord = spatial_report.get("coordinate_summary", {})
        preview = spatial_report.get("coordinate_preview", [])
        plt.figure(figsize=(5, 4))
        if preview:
            rows = [item["row"] for item in preview]
            cols = [item["col"] for item in preview]
            plt.scatter(cols, rows, s=8, alpha=0.6)
            plt.gca().invert_yaxis()
            plt.xlabel(str(coord.get("col_key")))
            plt.ylabel(str(coord.get("row_key")))
            plt.text(0.02, 0.02, f"risk={spatial_report.get('spatial_risk')}", transform=plt.gca().transAxes)
        else:
            plt.text(0.5, 0.5, "No valid coordinates", ha="center")
            plt.axis("off")
        plt.title("Spatial Audit")
        save("spatial_layout.png", "Spatial audit")

    if perturb_report and perturb_report.get("available"):
        top = perturb_report.get("top_perturbations", {})
        plt.figure(figsize=(5, 3.5))
        labels = list(top.keys())[:12]
        values = [top[label] for label in labels]
        if labels:
            plt.bar(labels, values)
            plt.xticks(rotation=45, ha="right")
            plt.ylabel("cells")
        else:
            plt.text(0.5, 0.5, "No perturbation groups", ha="center")
        plt.title("Perturbation Groups")
        save("perturbation_groups.png", "Perturbation groups")

    return figures


def _plot_value(value) -> float:
    if value is None:
        return 0.0
    try:
        if not np.isfinite(float(value)):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
