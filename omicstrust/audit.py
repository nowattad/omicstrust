from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from omicstrust.baselines.pca import run_pca_baseline
from omicstrust.baselines.truncated_svd import run_truncated_svd_baseline
from omicstrust.ingest import load_dataset
from omicstrust.nulls.calibration import null_calibration_diagnostics
from omicstrust.nulls.empirical_null import EmpiricalNull
from omicstrust.observability.qc_metrics import compute_qc_report, large_matrix_warnings, qc_augmented_obs
from omicstrust.perturb.audit import compute_perturb_report
from omicstrust.preprocessing import preprocess_with_audit
from omicstrust.reports.executive_summary import build_summary
from omicstrust.reports.figures import generate_required_figures
from omicstrust.reports.claim_matrix import build_claim_matrix
from omicstrust.reports.html_report import write_html_report
from omicstrust.reports.markdown_report import write_reviewer_report
from omicstrust.reports.pdf_report import write_pdf_report
from omicstrust.risk.batch_effect import component_covariate_associations, detect_batch_dominated_components
from omicstrust.risk.failure_modes import build_failure_report
from omicstrust.signal.ssi_engine import SSIEngine
from omicstrust.spatial.audit import compute_spatial_report
from omicstrust.trust import build_trust_report
from omicstrust.utils.memory import peak_memory_mb
from omicstrust.utils.serialization import make_json_safe, write_json, write_table_csv
from omicstrust.utils.timing import now, runtime_seconds
from omicstrust.workflows.evidence_ledger import build_evidence_ledger
from omicstrust.workflows.provenance import write_provenance


def run_audit(
    input_path: str | Path,
    *,
    output: str | Path,
    batch_key: str | None = None,
    donor_key: str | None = None,
    label_key: str | None = None,
    config_path: str | Path | None = None,
    command: list[str] | None = None,
) -> dict[str, Any]:
    start = now()
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "artifacts").mkdir(exist_ok=True)
    config = load_config(config_path)
    config.setdefault("data", {})["path"] = str(input_path)
    config.setdefault("project", {})["output_dir"] = str(output_dir)
    if batch_key is not None:
        config.setdefault("keys", {})["batch_key"] = batch_key
    if donor_key is not None:
        config.setdefault("keys", {})["donor_key"] = donor_key
    if label_key is not None:
        config.setdefault("keys", {})["label_key"] = label_key
    random_state = int(config.get("project", {}).get("random_state", 0))
    keys = config.get("keys", {})
    batch_key = keys.get("batch_key")
    donor_key = keys.get("donor_key")
    label_key = keys.get("label_key")

    dataset = load_dataset(
        input_path,
        layer=config.get("data", {}).get("layer"),
        use_raw=bool(config.get("data", {}).get("use_raw", False)),
    )
    qc_report = compute_qc_report(dataset, batch_key=batch_key, donor_key=donor_key, label_key=label_key)
    matrix_warnings = large_matrix_warnings(dataset.X.shape, config.get("preprocessing", {}))
    if matrix_warnings:
        qc_report["warnings"] = list(qc_report.get("warnings", [])) + matrix_warnings
        if qc_report.get("qc_status") == "pass":
            qc_report["qc_status"] = "warning"
    obs_aug = qc_augmented_obs(dataset)
    obs_for_metadata = dataset.obs if dataset.obs is not None else pd.DataFrame(index=range(dataset.X.shape[0]))
    metadata_assessment = _metadata_assessment(obs_for_metadata, batch_key=batch_key, donor_key=donor_key, label_key=label_key)
    X_processed, var_processed, preprocessing_report = preprocess_with_audit(
        dataset.X,
        config.get("preprocessing", {}),
        obs=obs_aug,
        var=dataset.var,
    )

    signal_config = config.get("signal", {})
    n_components = int(signal_config.get("n_components", 20))

    def engine_factory() -> SSIEngine:
        return SSIEngine(
            n_components=n_components,
            covariance=str(signal_config.get("covariance", "weighted")),
            solver=str(signal_config.get("solver", "auto")),
            regularization=float(signal_config.get("regularization", 1e-8)),
            random_state=random_state,
        )

    engine = engine_factory().fit(X_processed)
    signal_report = engine.diagnostics()
    signal_report["scores_shape"] = list(engine.scores_.shape)
    signal_report["preprocessing"] = preprocessing_report
    component_artifacts = _write_component_artifacts(output_dir, engine, obs_aug, var_processed)
    spatial_report = compute_spatial_report(obs_aug, engine.scores_)
    perturb_report = compute_perturb_report(obs_aug, engine.scores_)

    null_config = config.get("nulls", {})
    if bool(null_config.get("enabled", True)):
        null = EmpiricalNull(
            method=str(null_config.get("method", "within_batch_permutation")),
            n_permutations=int(null_config.get("n_permutations", 20)),
            quantile=float(null_config.get("quantile", 0.95)),
            random_state=random_state,
            n_jobs=int(null_config.get("n_jobs", 1)),
        ).fit(
            X_processed,
            engine_factory,
            batch=obs_aug[batch_key] if batch_key and batch_key in obs_aug.columns else None,
            labels=obs_aug[label_key] if label_key and label_key in obs_aug.columns else None,
        )
        null_report = null.summary(engine.spectrum())
        calibration_diagnostics = null_calibration_diagnostics(
            int(null_config.get("n_permutations", 20)),
            null_report.get("empirical_p_values", []),
        )
        null_report["calibration_status"] = calibration_diagnostics["status"]
        null_report["calibration_diagnostics"] = calibration_diagnostics
    else:
        null_report = {
            "method": "disabled",
            "n_permutations": 0,
            "quantile": None,
            "null_median": [],
            "null_threshold": [],
            "empirical_p_values": [],
            "components_above_null": [],
            "n_components_above_null": 0,
            "calibration_status": "underpowered",
            "warnings": ["Empirical null validation was disabled by configuration."],
        }

    technical_covariates = list(keys.get("technical_covariates", []))
    covariate_keys = [k for k in [batch_key, donor_key, label_key, *technical_covariates] if k]
    associations = component_covariate_associations(engine.scores_, obs_aug, covariate_keys)
    dominated = detect_batch_dominated_components(
        associations,
        threshold=float(config.get("risk", {}).get("batch_association_threshold", 0.5)),
        batch_keys=[k for k in [batch_key, donor_key] if k],
        label_key=label_key,
    )
    components = dominated.replace({np.nan: None}).to_dict(orient="records")
    max_batch_r2 = _safe_max([c.get("max_batch_r2") for c in components])
    if not metadata_assessment["batch_risk_assessable"] and not metadata_assessment["donor_risk_assessable"]:
        overall_risk = "unknown"
        components = [
            {
                "component": component_idx + 1,
                "risk": "unknown",
                "decision": "metadata_required",
                "max_batch_r2": None,
                "label_r2": None,
            }
            for component_idx in range(engine.scores_.shape[1])
        ]
    else:
        overall_risk = "high" if any(c.get("risk") == "high" for c in components) else "moderate" if any(c.get("risk") == "moderate" for c in components) else "low"
    batch_risk_report = {
        "components": components,
        "associations": associations.replace({np.nan: None}).to_dict(orient="records"),
        "max_batch_r2": max_batch_r2,
        "overall_risk": overall_risk,
        "batch_risk": "unknown" if not metadata_assessment["batch_risk_assessable"] else overall_risk,
        "donor_risk": "unknown" if not metadata_assessment["donor_risk_assessable"] else overall_risk,
        "label_assessment": "not_assessable" if not metadata_assessment["label_assessable"] else "assessable",
        "metadata_assessment": metadata_assessment,
    }

    stability_config = config.get("stability", {})
    if bool(stability_config.get("enabled", True)):
        from omicstrust.stability.bootstrap import StabilityAnalyzer

        stability_report = StabilityAnalyzer(
            n_bootstraps=int(stability_config.get("n_bootstraps", 8)),
            subsample_fraction=float(stability_config.get("subsample_fraction", 0.8)),
            random_state=random_state,
        ).fit(X_processed, engine_factory).summary()
    else:
        stability_report = {
            "mean_subspace_similarity": 0.0,
            "rank_mode": 0,
            "rank_std": 0.0,
            "stability_status": "insufficient_information",
            "warnings": ["Stability analysis was disabled by configuration."],
        }

    benchmark_rows = _run_baselines(
        X_processed,
        obs_aug,
        batch_key=batch_key,
        n_components=n_components,
        signal_score=float(signal_report.get("signal_score", 0.0)),
    )
    failure_report = build_failure_report(
        qc_report=qc_report,
        signal_report=signal_report,
        null_report=null_report,
        batch_risk_report=batch_risk_report,
        stability_report=stability_report,
        metadata_assessment=metadata_assessment,
        benchmark_rows=benchmark_rows,
    )
    reproducibility_report = {
        "status": "captured",
        "exact_reproduction": None,
        "message": "Provenance captured during audit. Run 'omicstrust reproduce <run_dir>' for a reproduction check.",
    }
    trust_report = build_trust_report(
        qc_report=qc_report,
        signal_report=signal_report,
        null_report=null_report,
        batch_risk_report=batch_risk_report,
        stability_report=stability_report,
        reproducibility_report=reproducibility_report,
        failure_report=failure_report,
    )
    summary = build_summary(
        qc_report=qc_report,
        signal_report=signal_report,
        null_report=null_report,
        batch_risk_report=batch_risk_report,
        stability_report=stability_report,
        trust_report=trust_report,
        failure_report=failure_report,
    )
    metrics_rows = _metrics_rows(
        qc_report=qc_report,
        signal_report=signal_report,
        null_report=null_report,
        batch_risk_report=batch_risk_report,
        stability_report=stability_report,
        spatial_report=spatial_report,
        perturb_report=perturb_report,
        trust_report=trust_report,
        runtime=runtime_seconds(start),
    )

    _write_config(output_dir / "config_used.yaml", config)
    provenance = write_provenance(
        output_dir,
        input_path=str(input_path),
        config=config,
        random_state=random_state,
        command=command or sys.argv,
    )
    claim_context = {
        "summary": summary,
        "qc_report": qc_report,
        "metadata_assessment": metadata_assessment,
        "signal_report": signal_report,
        "null_report": null_report,
        "batch_risk_report": batch_risk_report,
        "stability_report": stability_report,
        "failure_report": failure_report,
        "trust_report": trust_report,
        "provenance": provenance,
    }
    claim_matrix = build_claim_matrix(claim_context)
    figures = generate_required_figures(
        output_dir,
        qc_report=qc_report,
        signal_report=signal_report,
        null_report=null_report,
        batch_risk_report=batch_risk_report,
        stability_report=stability_report,
        benchmark_rows=benchmark_rows,
        failure_report=failure_report,
        spatial_report=spatial_report,
        perturb_report=perturb_report,
        dpi=int(config.get("reports", {}).get("dpi", 150)),
    )
    context = {
        "summary": summary,
        "qc_report": qc_report,
        "metadata_assessment": metadata_assessment,
        "signal_report": signal_report,
        "spatial_report": spatial_report,
        "perturb_report": perturb_report,
        "null_report": null_report,
        "batch_risk_report": batch_risk_report,
        "stability_report": stability_report,
        "reproducibility_report": reproducibility_report,
        "failure_report": failure_report,
        "trust_report": trust_report,
        "benchmark_rows": benchmark_rows,
        "metrics_rows": metrics_rows,
        "figures": figures,
        "provenance": provenance,
        "component_artifacts": component_artifacts,
        "claim_matrix": claim_matrix,
    }
    context["evidence_ledger"] = build_evidence_ledger(context=context, config=config)
    _write_reports(output_dir, context)
    return make_json_safe(context)


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    default_path = Path(__file__).resolve().parent.parent / "configs" / "singlecell_audit.yaml"
    path = Path(config_path) if config_path else default_path
    if not path.exists():
        return _default_config()
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _merge_dicts(_default_config(), loaded)


def save_config_used(path: str | Path, config: dict[str, Any]) -> None:
    _write_config(path, config)


def _write_reports(output_dir: Path, context: dict[str, Any]) -> None:
    write_json(output_dir / "summary.json", context["summary"])
    write_json(output_dir / "claim_matrix.json", context["claim_matrix"])
    write_json(output_dir / "evidence_ledger.json", context["evidence_ledger"])
    write_json(output_dir / "component_artifacts.json", context["component_artifacts"])
    write_json(output_dir / "trust_report.json", context["trust_report"])
    write_json(output_dir / "qc_report.json", context["qc_report"])
    write_json(output_dir / "metadata_assessment.json", context["metadata_assessment"])
    write_json(output_dir / "signal_report.json", context["signal_report"])
    write_json(output_dir / "spatial_report.json", context["spatial_report"])
    write_json(output_dir / "perturb_report.json", context["perturb_report"])
    write_json(output_dir / "null_report.json", context["null_report"])
    write_json(output_dir / "batch_risk_report.json", context["batch_risk_report"])
    write_json(output_dir / "stability_report.json", context["stability_report"])
    write_json(output_dir / "reproducibility_report.json", context["reproducibility_report"])
    write_json(output_dir / "failure_report.json", context["failure_report"])
    write_table_csv(output_dir / "benchmark_report.csv", context["benchmark_rows"])
    write_table_csv(output_dir / "metrics.csv", context["metrics_rows"])
    write_html_report(output_dir / "report.html", context)
    write_reviewer_report(output_dir / "reviewer_report.md", context)
    try:
        write_pdf_report(output_dir / "report.pdf", context)
    except NotImplementedError as exc:
        (output_dir / "report_pdf_unavailable.txt").write_text(str(exc) + "\n", encoding="utf-8")


def _run_baselines(X, obs, *, batch_key: str | None, n_components: int, signal_score: float) -> list[dict[str, Any]]:
    rows = [
        {
            "method": "SSI",
            "runtime_seconds": None,
            "memory_mb": peak_memory_mb(),
            "batch_risk": None,
            "stability": None,
            "signal_score": signal_score,
        }
    ]
    for runner in (run_pca_baseline, run_truncated_svd_baseline):
        try:
            rows.append(runner(X, obs=obs, batch_key=batch_key, n_components=n_components))
        except Exception as exc:
            rows.append(
                {
                    "method": runner.__name__.replace("run_", "").replace("_baseline", ""),
                    "runtime_seconds": None,
                    "memory_mb": peak_memory_mb(),
                    "batch_risk": None,
                    "stability": None,
                    "signal_score": None,
                    "warning": str(exc),
                }
            )
    return make_json_safe(rows)


def _write_component_artifacts(output_dir: Path, engine: SSIEngine, obs: pd.DataFrame, var: pd.DataFrame | None) -> dict[str, Any]:
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scores = pd.DataFrame(
        engine.scores_,
        index=[str(idx) for idx in obs.index] if obs is not None else None,
        columns=[f"component_{i + 1}" for i in range(engine.scores_.shape[1])],
    )
    scores.index.name = "observation_id"
    scores_path = artifacts_dir / "component_scores.csv"
    scores.to_csv(scores_path)

    components = engine.components()
    if var is not None and len(var) == components.shape[1]:
        feature_index = [str(idx) for idx in var.index]
    else:
        feature_index = [f"feature_{i}" for i in range(components.shape[1])]
    loadings = pd.DataFrame(
        components.T,
        index=feature_index,
        columns=[f"component_{i + 1}" for i in range(components.shape[0])],
    )
    loadings.index.name = "feature_id"
    loadings_path = artifacts_dir / "component_loadings.csv"
    loadings.to_csv(loadings_path)
    return {
        "component_scores": str(scores_path.relative_to(output_dir)),
        "component_loadings": str(loadings_path.relative_to(output_dir)),
        "n_components": int(components.shape[0]),
        "n_features": int(components.shape[1]),
    }


def _metrics_rows(**reports) -> list[dict[str, Any]]:
    rows = [{"metric": "runtime_seconds", "value": reports["runtime"]}]
    rows.append({"metric": "trust_score", "value": reports["trust_report"].get("trust_score")})
    rows.append({"metric": "n_cells", "value": reports["qc_report"].get("n_cells")})
    rows.append({"metric": "n_features", "value": reports["qc_report"].get("n_features")})
    rows.append({"metric": "signal_score", "value": reports["signal_report"].get("signal_score")})
    rows.append({"metric": "n_components_above_null", "value": reports["null_report"].get("n_components_above_null")})
    rows.append({"metric": "max_batch_r2", "value": reports["batch_risk_report"].get("max_batch_r2")})
    rows.append({"metric": "mean_subspace_similarity", "value": reports["stability_report"].get("mean_subspace_similarity")})
    if "spatial_report" in reports:
        rows.append({"metric": "spatial_max_coordinate_r2", "value": reports["spatial_report"].get("max_coordinate_r2")})
    if "perturb_report" in reports:
        rows.append({"metric": "perturb_max_r2", "value": reports["perturb_report"].get("max_perturbation_r2")})
    return rows


def _default_config() -> dict[str, Any]:
    return {
        "project": {"name": "omicstrust_full_audit", "output_dir": "results/study_001", "random_state": 42},
        "data": {"path": None, "layer": None, "use_raw": False},
        "keys": {
            "batch_key": None,
            "donor_key": None,
            "label_key": None,
            "technical_covariates": ["total_counts", "pct_counts_mt", "n_genes_by_counts"],
        },
        "preprocessing": {
            "enabled": True,
            "normalize_total": True,
            "target_sum": 10000,
            "log1p": True,
            "hvg_selection": True,
            "n_top_genes": 500,
            "scale": True,
            "residualize": False,
        },
        "signal": {"method": "ssi", "n_components": 10, "covariance": "weighted", "solver": "auto", "regularization": 1e-8},
        "nulls": {"enabled": True, "method": "within_batch_permutation", "n_permutations": 20, "quantile": 0.95, "n_jobs": 1},
        "risk": {"batch_association_threshold": 0.5, "technical_covariate_threshold": 0.5},
        "stability": {"enabled": True, "n_bootstraps": 8, "subsample_fraction": 0.8},
        "baselines": {"pca": True, "truncated_svd": True, "factor_analysis": False, "scanpy": False, "scvi_audit": False, "harmony_audit": False},
        "reports": {"html": True, "markdown": True, "json": True, "figures": True, "dpi": 150},
        "reproducibility": {"capture_environment": True, "capture_package_versions": True, "save_input_fingerprint": True},
    }


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _write_config(path: str | Path, config: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(make_json_safe(config), handle, sort_keys=False)


def _safe_max(values) -> float:
    finite = [float(v) for v in values if v is not None and np.isfinite(float(v))]
    return max(finite) if finite else 0.0


def _metadata_assessment(obs: pd.DataFrame, *, batch_key: str | None, donor_key: str | None, label_key: str | None) -> dict[str, Any]:
    obs_columns = [str(column) for column in obs.columns]
    batch_available = bool(batch_key and batch_key in obs.columns)
    donor_available = bool(donor_key and donor_key in obs.columns)
    label_available = bool(label_key and label_key in obs.columns)
    missing = []
    if not batch_available:
        missing.append("missing_batch_metadata")
    if not donor_available:
        missing.append("missing_donor_metadata")
    if not label_available:
        missing.append("missing_label_metadata")
    return {
        "batch_key": batch_key,
        "donor_key": donor_key,
        "label_key": label_key,
        "batch_key_available": batch_available,
        "donor_key_available": donor_available,
        "label_key_available": label_available,
        "batch_risk_assessable": batch_available,
        "donor_risk_assessable": donor_available,
        "label_assessable": label_available,
        "obs_columns": obs_columns,
        "missing_metadata_warnings": missing,
        "interpretation_limited": bool(missing),
        "all_core_metadata_missing": not batch_available and not donor_available and not label_available,
    }
