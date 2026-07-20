from __future__ import annotations

from pathlib import Path
from typing import Any


def write_reviewer_report(path: str | Path, context: dict[str, Any]) -> None:
    summary = context["summary"]
    failures = context["failure_report"].get("failures", [])
    claims = context.get("claim_matrix", {})
    ledger = context.get("evidence_ledger", {})
    lines = [
        "# OmicsTrust / CellAudit Reviewer Report",
        "",
        "This report audits statistical structure, empirical-null support, batch/confounding risk, stability, and reproducibility. It does not claim automatic biological discovery.",
        "",
        "## Summary",
        "",
        f"- Data QC: {summary.get('data_qc')}",
        f"- Structural signal: {summary.get('structural_signal')}",
        f"- Empirical null: {summary.get('empirical_null')}",
        f"- Batch risk: {summary.get('batch_risk')}",
        f"- Stability: {summary.get('stability')}",
        f"- Trust level: {summary.get('trust_level')}",
        f"- Safe to interpret: {summary.get('safe_to_interpret')}",
        "",
        "## Specialized Audits",
        "",
        f"- Spatial audit: {_availability(context.get('spatial_report', {}))}",
        f"- Perturb-seq audit: {_availability(context.get('perturb_report', {}))}",
        "",
        "## Main Recommendation",
        "",
        str(summary.get("recommendation")),
        "",
        "## What Can Be Claimed",
        "",
    ]
    lines.extend([f"- {item}" for item in claims.get("can_claim", [])] or ["- Not available."])
    lines.extend(
        [
            "",
            "## What Cannot Be Claimed",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in claims.get("cannot_claim", [])] or ["- Not available."])
    lines.extend(
        [
            "",
            "## Evidence Ledger",
            "",
            f"- Run ID: {ledger.get('run_id')}",
            f"- Config fingerprint: {ledger.get('config_fingerprint')}",
            f"- Reproducibility status: {ledger.get('reproducibility_status')}",
            f"- RUO: {claims.get('ruo_disclaimer', ledger.get('ruo_disclaimer'))}",
            "",
        ]
    )
    lines.extend(
        [
        "## Failure Modes",
        "",
        ]
    )
    if failures:
        for failure in failures:
            lines.extend(
                [
                    f"### {failure['failure_type']}",
                    "",
                    f"- Severity: {failure['severity']}",
                    f"- Interpretation: {failure['interpretation']}",
                    f"- Recommendation: {failure['recommendation']}",
                    "",
                ]
            )
    else:
        lines.append("No high-confidence failure modes were detected by the configured audit.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _availability(report: dict[str, Any]) -> str:
    if report.get("available"):
        return "available"
    return f"not available ({report.get('reason', 'not computed')})"
