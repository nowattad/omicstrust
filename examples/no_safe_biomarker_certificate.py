from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from numbers import Integral, Real
from typing import Any


def _json_safe(value: Any) -> Any:
    """Convert NaN/Infinity and numpy-like values into strict JSON-safe values."""
    if value is None:
        return None
    if isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _load_json_files(run_dir: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        docs.append({"path": str(path), "payload": payload})
    return docs


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}.{i}" if prefix else str(i)
            out.update(_flatten(v, key))
    else:
        out[prefix] = obj
    return out


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip().lower()


def _find_values(flat: dict[str, Any], *key_fragments: str) -> list[tuple[str, Any]]:
    hits: list[tuple[str, Any]] = []
    fragments = [f.lower() for f in key_fragments]
    for k, v in flat.items():
        lk = k.lower()
        if all(f in lk for f in fragments):
            hits.append((k, v))
    return hits


def _has_bad_value(values: list[tuple[str, Any]], bad_terms: set[str]) -> bool:
    for _, v in values:
        sv = _stringify(v)
        if sv in bad_terms:
            return True
        if any(term in sv for term in bad_terms):
            return True
    return False


def build_certificate(run_dir: Path) -> dict[str, Any]:
    docs = _load_json_files(run_dir)
    flat: dict[str, Any] = {}

    for doc in docs:
        path = doc["path"]
        payload = doc["payload"]
        for k, v in _flatten(payload).items():
            flat[f"{path}::{k}"] = v

    evidence: dict[str, Any] = {
        "json_files_scanned": [d["path"] for d in docs],
        "json_file_count": len(docs),
    }

    safe_values = _find_values(flat, "safe", "interpret")
    trust_values = _find_values(flat, "trust")
    failure_values = _find_values(flat, "failure")
    batch_values = _find_values(flat, "batch")
    donor_values = _find_values(flat, "donor")
    null_values = _find_values(flat, "null")
    stability_values = _find_values(flat, "stability")
    validation_values = _find_values(flat, "validation")

    reasons: list[str] = []

    unsafe_terms = {
        "false",
        "no",
        "unsafe",
        "not_safe",
        "not safe",
        "limited",
        "blocked",
        "failed",
        "fail",
    }

    high_risk_terms = {
        "high",
        "severe",
        "dominant",
        "dominated",
        "confounded",
        "confounding",
        "unsafe",
        "blocked",
        "failed",
        "fail",
    }

    if _has_bad_value(safe_values, unsafe_terms):
        reasons.append("safe_to_interpret_false_or_limited")

    if _has_bad_value(trust_values, {"unsafe", "low", "limited", "blocked"}):
        reasons.append("trust_level_not_sufficient_for_biomarker_claim")

    if _has_bad_value(failure_values, high_risk_terms):
        reasons.append("main_failure_mode_blocks_claim")

    if _has_bad_value(batch_values, high_risk_terms):
        reasons.append("batch_or_technical_confounding_risk")

    if _has_bad_value(donor_values, high_risk_terms):
        reasons.append("donor_or_subject_confounding_risk")

    if _has_bad_value(null_values, {"failed", "fail", "not_passed", "not passed"}):
        reasons.append("empirical_null_not_passed")

    if _has_bad_value(stability_values, {"low", "unstable", "failed", "fail"}):
        reasons.append("stability_not_sufficient")

    has_locked_validation = bool(validation_values)
    if not has_locked_validation:
        reasons.append("locked_external_validation_not_found")

    # Conservative RUO decision policy:
    # Any explicit unsafe/blocked/confounded signal means no biomarker claim is safe.
    hard_blockers = {
        "safe_to_interpret_false_or_limited",
        "trust_level_not_sufficient_for_biomarker_claim",
        "main_failure_mode_blocks_claim",
        "batch_or_technical_confounding_risk",
        "donor_or_subject_confounding_risk",
        "empirical_null_not_passed",
        "stability_not_sufficient",
    }

    if any(r in hard_blockers for r in reasons):
        decision = "no_safe_biomarker_claim_found"
    elif "locked_external_validation_not_found" in reasons:
        decision = "insufficient_evidence_for_biomarker_claim"
    else:
        decision = "candidate_ruo_claim_requires_human_review"

    certificate = {
        "workflow": "no_safe_biomarker_claim_certificate",
        "input_run_dir": str(run_dir),
        "status": "completed",
        "decision": decision,
        "biomarker_claim_allowed": decision == "candidate_ruo_claim_requires_human_review",
        "ruo_only": True,
        "clinical_use_allowed": False,
        "reasons": reasons,
        "evidence_summary": evidence,
        "claim_matrix": {
            "can_claim": [
                "The workflow scanned OmicsTrust JSON evidence from an audit run.",
                "The workflow issued a conservative RUO biomarker-claim certificate.",
                "The workflow checked for safe-interpretation, trust, failure-mode, batch, donor, null, stability, and validation evidence when present.",
            ],
            "cannot_claim": [
                "This certificate does not validate a clinical biomarker.",
                "This certificate does not support diagnosis, treatment selection, or patient management.",
                "A detected signal is not automatically a safe biological or biomarker claim.",
                "Absence of detected blockers in available JSON is not equivalent to prospective validation.",
            ],
            "next_actions": [
                "Review the audit report and failure hierarchy.",
                "Run locked validation on an independent dataset before escalating any claim.",
                "Require domain review before any biological interpretation.",
            ],
        },
    }

    return _json_safe(certificate)


def write_markdown(certificate: dict[str, Any], path: Path) -> None:
    lines = [
        "# No-Safe-Biomarker Claim Certificate",
        "",
        f"**Decision:** `{certificate['decision']}`",
        "",
        f"**Biomarker claim allowed:** `{certificate['biomarker_claim_allowed']}`",
        "",
        f"**RUO only:** `{certificate['ruo_only']}`",
        "",
        f"**Clinical use allowed:** `{certificate['clinical_use_allowed']}`",
        "",
        "## Reasons",
        "",
    ]

    for reason in certificate["reasons"]:
        lines.append(f"- `{reason}`")

    lines += [
        "",
        "## Claim Matrix",
        "",
        "### Can claim",
        "",
    ]

    for item in certificate["claim_matrix"]["can_claim"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "### Cannot claim",
        "",
    ]

    for item in certificate["claim_matrix"]["cannot_claim"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "### Next actions",
        "",
    ]

    for item in certificate["claim_matrix"]["next_actions"]:
        lines.append(f"- {item}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a conservative RUO no-safe-biomarker claim certificate from an OmicsTrust audit output directory."
    )
    parser.add_argument("run_dir", help="OmicsTrust audit output directory containing JSON files.")
    parser.add_argument(
        "--output",
        default="results/no_safe_biomarker_certificate",
        help="Output directory for certificate JSON/Markdown.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not run_dir.exists():
        raise SystemExit(f"Input run directory does not exist: {run_dir}")

    certificate = build_certificate(run_dir)

    json_path = out_dir / "no_safe_biomarker_certificate.json"
    md_path = out_dir / "no_safe_biomarker_certificate.md"

    json_path.write_text(
        json.dumps(certificate, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    write_markdown(certificate, md_path)

    print(json.dumps(certificate, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
