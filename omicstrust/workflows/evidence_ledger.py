from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omicstrust.utils.serialization import make_json_safe, write_json


def build_evidence_ledger(*, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    provenance = context.get("provenance", {})
    qc = context.get("qc_report", {})
    null_report = context.get("null_report", {})
    failure = context.get("failure_report", {})
    trust = context.get("trust_report", {})
    summary = context.get("summary", {})
    metadata = context.get("metadata_assessment", {})

    warnings = []
    for report_name in ("qc_report", "null_report", "stability_report"):
        report = context.get(report_name, {})
        warnings.extend(str(w) for w in report.get("warnings", []) or [])
    warnings.extend(str(w) for w in metadata.get("missing_metadata_warnings", []) or [])

    config_safe = make_json_safe(config)
    return {
        "ledger_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": provenance.get("command_history", {}).get("run_id"),
        "input_fingerprints": provenance.get("input_fingerprints", {}),
        "config_fingerprint": _fingerprint_json(config_safe),
        "package_versions": provenance.get("package_versions", {}),
        "environment": provenance.get("environment", {}),
        "random_seeds": provenance.get("random_seeds", {}),
        "summary": summary,
        "trust": {
            "trust_score": trust.get("trust_score"),
            "trust_level": trust.get("trust_level"),
            "final_decision": trust.get("final_decision"),
            "safe_to_interpret": trust.get("safe_to_interpret"),
            "safe_to_interpret_biologically": trust.get("safe_to_interpret_biologically"),
        },
        "null_evidence": {
            "method": null_report.get("method"),
            "n_permutations": null_report.get("n_permutations"),
            "calibration_status": null_report.get("calibration_status"),
            "n_components_above_null": null_report.get("n_components_above_null"),
            "empirical_p_values": null_report.get("empirical_p_values", []),
        },
        "metadata_evidence": metadata,
        "qc_warnings": qc.get("warnings", []),
        "warnings": sorted(set(warnings)),
        "failure_modes": failure.get("failures", []),
        "reproducibility_status": context.get("reproducibility_report", {}).get("status"),
        "ruo_disclaimer": "Research Use Only. Not for diagnosis, prognosis, treatment selection, or regulated clinical decision-making.",
    }


def write_evidence_ledger(path: str | Path, *, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    ledger = build_evidence_ledger(context=context, config=config)
    write_json(path, ledger)
    return ledger


def _fingerprint_json(value: Any) -> str:
    payload = json.dumps(make_json_safe(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
