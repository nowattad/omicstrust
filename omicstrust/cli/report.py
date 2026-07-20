from __future__ import annotations

from pathlib import Path

import pandas as pd

from omicstrust.reports.claim_matrix import build_claim_matrix
from omicstrust.reports.html_report import write_html_report
from omicstrust.reports.markdown_report import write_reviewer_report
from omicstrust.reports.pdf_report import write_pdf_report
from omicstrust.utils.serialization import read_json


def regenerate_report(run_dir: str | Path) -> None:
    run_dir = Path(run_dir)
    context = {
        "summary": read_json(run_dir / "summary.json"),
        "qc_report": read_json(run_dir / "qc_report.json"),
        "metadata_assessment": read_json(run_dir / "metadata_assessment.json") if (run_dir / "metadata_assessment.json").exists() else {},
        "signal_report": read_json(run_dir / "signal_report.json"),
        "spatial_report": read_json(run_dir / "spatial_report.json") if (run_dir / "spatial_report.json").exists() else {"available": False, "reason": "not computed"},
        "perturb_report": read_json(run_dir / "perturb_report.json") if (run_dir / "perturb_report.json").exists() else {"available": False, "reason": "not computed"},
        "null_report": read_json(run_dir / "null_report.json"),
        "batch_risk_report": read_json(run_dir / "batch_risk_report.json"),
        "stability_report": read_json(run_dir / "stability_report.json"),
        "reproducibility_report": read_json(run_dir / "reproducibility_report.json"),
        "failure_report": read_json(run_dir / "failure_report.json"),
        "trust_report": read_json(run_dir / "trust_report.json"),
        "claim_matrix": read_json(run_dir / "claim_matrix.json") if (run_dir / "claim_matrix.json").exists() else {},
        "evidence_ledger": read_json(run_dir / "evidence_ledger.json") if (run_dir / "evidence_ledger.json").exists() else {},
        "component_artifacts": read_json(run_dir / "component_artifacts.json") if (run_dir / "component_artifacts.json").exists() else {},
        "benchmark_rows": pd.read_csv(run_dir / "benchmark_report.csv").to_dict(orient="records"),
        "metrics_rows": pd.read_csv(run_dir / "metrics.csv").to_dict(orient="records"),
        "figures": [
            {"path": f"figures/{p.name}", "title": p.stem.replace("_", " ").title()}
            for p in sorted((run_dir / "figures").glob("*.png"))
        ],
    }
    if not context["claim_matrix"]:
        context["claim_matrix"] = build_claim_matrix(context)
    write_html_report(run_dir / "report.html", context)
    write_reviewer_report(run_dir / "reviewer_report.md", context)
    try:
        write_pdf_report(run_dir / "report.pdf", context)
    except NotImplementedError as exc:
        (run_dir / "report_pdf_unavailable.txt").write_text(str(exc) + "\n", encoding="utf-8")
