from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from omicstrust.audit import load_config, run_audit
from omicstrust.ingest import load_dataset
from omicstrust.preprocessing import preprocess_with_audit
from omicstrust.risk.batch_effect import component_covariate_associations
from omicstrust.utils.serialization import read_json, write_json
from omicstrust.utils.validation import to_dense_safe


def lock_axis_from_run(
    run_dir: str | Path,
    *,
    output: str | Path,
    axis_name: str,
    component: int = 1,
    hypothesis: str = "",
    allowed_claim: str = "RUO locked-axis candidate for external validation.",
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    loadings_path = run_dir / "artifacts" / "component_loadings.csv"
    if not loadings_path.exists():
        raise FileNotFoundError(f"Missing component loadings: {loadings_path}. Rerun audit with the current OmicsTrust version.")
    loadings = pd.read_csv(loadings_path, index_col=0)
    column = f"component_{int(component)}"
    if column not in loadings.columns:
        raise ValueError(f"Component {component} is not available in {loadings_path}.")

    axis_loadings = loadings[[column]].rename(columns={column: "loading"})
    axis_loadings.to_csv(output / "locked_axis_loadings.csv")
    top = (
        axis_loadings.assign(abs_loading=axis_loadings["loading"].abs())
        .sort_values("abs_loading", ascending=False)
        .head(25)
        .drop(columns=["abs_loading"])
    )
    contract = {
        "axis_contract_version": "1.0",
        "axis_name": axis_name,
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_dir": str(run_dir),
        "component": int(component),
        "hypothesis": hypothesis,
        "allowed_claim": allowed_claim,
        "forbidden_claims": [
            "clinical biomarker",
            "treatment guidance",
            "diagnostic or prognostic device",
            "validated compact panel",
        ],
        "source_summary": read_json(run_dir / "summary.json") if (run_dir / "summary.json").exists() else {},
        "source_trust": read_json(run_dir / "trust_report.json") if (run_dir / "trust_report.json").exists() else {},
        "source_config": read_json(run_dir / "evidence_ledger.json").get("config_fingerprint") if (run_dir / "evidence_ledger.json").exists() else None,
        "loadings_file": "locked_axis_loadings.csv",
        "n_locked_features": int(axis_loadings.shape[0]),
        "top_features": [{"feature_id": str(idx), "loading": float(row["loading"])} for idx, row in top.iterrows()],
        "ruo_disclaimer": "Research Use Only. External validation is required before biological, clinical, or commercial claims.",
    }
    write_json(output / "locked_axis.json", contract)
    return contract


def validate_locked_axis(
    locked_axis: str | Path,
    input_path: str | Path,
    *,
    output: str | Path,
    batch_key: str | None = None,
    donor_key: str | None = None,
    label_key: str | None = None,
    config_path: str | Path | None = None,
    min_feature_coverage: float = 0.2,
) -> dict[str, Any]:
    lock_dir = _lock_dir(locked_axis)
    contract = read_json(lock_dir / "locked_axis.json")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    audit_dir = output / "audit"
    audit_context = run_audit(
        input_path,
        output=audit_dir,
        batch_key=batch_key,
        donor_key=donor_key,
        label_key=label_key,
        config_path=config_path,
        command=["omicstrust", "validate-axis", str(locked_axis), str(input_path)],
    )
    projection = _project_locked_axis(
        lock_dir / str(contract["loadings_file"]),
        input_path,
        config_path=config_path,
        label_key=label_key,
        batch_key=batch_key,
        donor_key=donor_key,
        scores_output=output / "locked_axis_scores.csv",
    )
    summary = audit_context.get("summary", {})
    feature_coverage = float(projection.get("feature_coverage", 0.0) or 0.0)
    passed = (
        projection.get("projected")
        and feature_coverage >= float(min_feature_coverage)
        and summary.get("structural_signal") == "detected"
        and summary.get("safe_to_interpret") == "yes"
    )
    if not projection.get("projected"):
        decision = "failed_axis_projection"
    elif feature_coverage < float(min_feature_coverage):
        decision = "insufficient_feature_overlap"
    elif summary.get("safe_to_interpret") != "yes":
        decision = "audit_not_safe_to_interpret"
    elif passed:
        decision = "locked_validation_passed_for_ruo_followup"
    else:
        decision = "locked_validation_inconclusive"

    report = {
        "validation_version": "1.0",
        "axis_name": contract.get("axis_name"),
        "input_path": str(input_path),
        "audit_dir": str(audit_dir),
        "decision": decision,
        "passed": bool(passed),
        "feature_coverage": feature_coverage,
        "projection": projection,
        "scores_file": "locked_axis_scores.csv" if (output / "locked_axis_scores.csv").exists() else None,
        "audit_summary": summary,
        "allowed_claim": "Locked-axis validation evidence for RUO follow-up only.",
        "forbidden_claims": contract.get("forbidden_claims", []),
        "recommendation": _validation_recommendation(decision),
        "ruo_disclaimer": contract.get("ruo_disclaimer"),
    }
    write_json(output / "locked_validation_report.json", report)
    return report


def _project_locked_axis(
    loadings_path: Path,
    input_path: str | Path,
    *,
    config_path: str | Path | None,
    label_key: str | None,
    batch_key: str | None,
    donor_key: str | None,
    scores_output: str | Path | None = None,
) -> dict[str, Any]:
    locked = pd.read_csv(loadings_path, index_col=0)["loading"].astype(float)
    config = load_config(config_path)
    dataset = load_dataset(
        input_path,
        layer=config.get("data", {}).get("layer"),
        use_raw=bool(config.get("data", {}).get("use_raw", False)),
    )
    obs = dataset.obs if dataset.obs is not None else pd.DataFrame(index=range(dataset.X.shape[0]))
    X_processed, var_processed, preprocessing_report = preprocess_with_audit(
        dataset.X,
        config.get("preprocessing", {}),
        obs=obs,
        var=dataset.var,
    )
    if var_processed is None:
        feature_names = pd.Index([f"feature_{i}" for i in range(X_processed.shape[1])])
    else:
        feature_names = pd.Index([str(idx) for idx in var_processed.index])
    common = feature_names.intersection(pd.Index([str(idx) for idx in locked.index]))
    coverage = float(len(common) / max(1, len(locked)))
    if len(common) < 2:
        return {
            "projected": False,
            "reason": "fewer_than_two_locked_features_overlap",
            "n_common_features": int(len(common)),
            "n_locked_features": int(len(locked)),
            "feature_coverage": coverage,
        }
    positions = [int(feature_names.get_loc(feature)) for feature in common]
    dense = to_dense_safe(X_processed, reason="locked axis projection")
    X_common = np.asarray(dense[:, positions], dtype=float)
    weights = locked.loc[common].to_numpy(dtype=float)
    norm = np.linalg.norm(weights)
    if not np.isfinite(norm) or norm <= 0:
        return {
            "projected": False,
            "reason": "locked_loadings_have_zero_norm",
            "n_common_features": int(len(common)),
            "n_locked_features": int(len(locked)),
            "feature_coverage": coverage,
        }
    scores = X_common @ (weights / norm)
    score_frame = pd.DataFrame({"locked_axis_score": scores}, index=obs.index)
    score_frame.index.name = "observation_id"
    if scores_output is not None:
        Path(scores_output).parent.mkdir(parents=True, exist_ok=True)
        score_frame.to_csv(scores_output)
    associations = []
    keys = [key for key in [batch_key, donor_key, label_key] if key]
    if keys:
        assoc = component_covariate_associations(score_frame.to_numpy(), obs, keys)
        associations = assoc.to_dict(orient="records")
    top_association = _top_association(associations)
    return {
        "projected": True,
        "n_common_features": int(len(common)),
        "n_locked_features": int(len(locked)),
        "feature_coverage": coverage,
        "score_mean": float(np.mean(scores)),
        "score_std": float(np.std(scores)),
        "score_min": float(np.min(scores)),
        "score_max": float(np.max(scores)),
        "preprocessing": preprocessing_report,
        "associations": associations,
        "top_metadata_association": top_association,
    }


def _lock_dir(path: str | Path) -> Path:
    path = Path(path)
    if path.is_dir():
        return path
    if path.name == "locked_axis.json":
        return path.parent
    raise ValueError("locked_axis must be a directory or a locked_axis.json file.")


def _validation_recommendation(decision: str) -> str:
    if decision == "locked_validation_passed_for_ruo_followup":
        return "Continue with independent cohort validation and keep all claims RUO-limited."
    if decision == "audit_not_safe_to_interpret":
        return "Do not advance the locked axis until audit failures, metadata gaps, or confounding risks are resolved."
    if decision == "insufficient_feature_overlap":
        return "Use a dataset with stronger feature overlap or lock an axis on a shared feature universe."
    if decision == "failed_axis_projection":
        return "Check feature identifiers, preprocessing compatibility, and locked loading integrity."
    return "Treat this validation as inconclusive and run additional prespecified checks."


def _top_association(associations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not associations:
        return None
    return max(associations, key=lambda row: float(row.get("r2", 0.0) or 0.0))
