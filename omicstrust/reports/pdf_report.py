from __future__ import annotations

from pathlib import Path
from typing import Any


def write_pdf_report(path: str | Path, context: dict[str, Any]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:  # pragma: no cover - exercised when optional dependency is absent.
        raise NotImplementedError("PDF export requires the optional dependency 'reportlab'.") from exc

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Cell", parent=styles["BodyText"], fontSize=8.5, leading=10.5))
    styles.add(ParagraphStyle(name="Muted", parent=styles["BodyText"], fontSize=8.5, leading=10.5, textColor=colors.HexColor("#56616f")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=13, leading=16, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="TitleBlock", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=10, textColor=colors.HexColor("#11263c")))

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title="OmicsTrust CellAudit Report",
        author="OmicsTrust",
    )
    story: list[Any] = []
    summary = context.get("summary", {})
    trust = context.get("trust_report", {})
    failures = context.get("failure_report", {}).get("failures", [])
    claims = context.get("claim_matrix", {})

    story.append(Paragraph("OmicsTrust / CellAudit Report", styles["TitleBlock"]))
    story.append(Paragraph("Scientific trust audit for omics data. Research Use Only.", styles["Muted"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(_kv_table([
        ("Data QC", summary.get("data_qc")),
        ("Structural Signal", summary.get("structural_signal")),
        ("Empirical Null", summary.get("empirical_null")),
        ("Batch Risk", summary.get("batch_risk")),
        ("Donor Risk", summary.get("donor_risk")),
        ("Label Assessment", summary.get("label_assessment")),
        ("Stability", summary.get("stability")),
        ("Trust Level", summary.get("trust_level")),
        ("Trust Score", trust.get("trust_score")),
        ("Safe To Interpret", summary.get("safe_to_interpret")),
        ("Main Failure", _humanize(summary.get("main_failure") or "none")),
    ], styles))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("Recommendation", styles["Section"]))
    story.append(Paragraph(_clean(summary.get("recommendation")), styles["BodyText"]))
    story.append(Paragraph("What Can Be Claimed", styles["Section"]))
    story.extend(_bullet_list(claims.get("can_claim", []), styles))
    story.append(Paragraph("What Cannot Be Claimed", styles["Section"]))
    story.extend(_bullet_list(claims.get("cannot_claim", []), styles))
    story.append(PageBreak())

    story.append(Paragraph("Failure Hierarchy", styles["Section"]))
    if failures:
        rows = [[_p("Failure", styles), _p("Severity", styles), _p("Interpretation", styles), _p("Recommendation", styles)]]
        for failure in failures:
            rows.append([
                _p(_humanize(failure.get("failure_type")), styles),
                _p(failure.get("severity"), styles),
                _p(failure.get("interpretation"), styles),
                _p(failure.get("recommendation"), styles),
            ])
        table = Table(rows, colWidths=[3.4 * cm, 2.0 * cm, 5.4 * cm, 5.4 * cm], repeatRows=1)
        table.setStyle(_table_style(header=True))
        story.append(table)
    else:
        story.append(Paragraph("No configured failure modes were detected.", styles["BodyText"]))

    story.append(Paragraph("Evidence Ledger", styles["Section"]))
    ledger = context.get("evidence_ledger", {})
    story.append(_kv_table([
        ("Run ID", ledger.get("run_id")),
        ("Config Fingerprint", ledger.get("config_fingerprint")),
        ("Reproducibility Status", ledger.get("reproducibility_status")),
        ("Null Method", ledger.get("null_evidence", {}).get("method")),
        ("Null Permutations", ledger.get("null_evidence", {}).get("n_permutations")),
        ("Null Calibration", ledger.get("null_evidence", {}).get("calibration_status")),
    ], styles))
    story.append(Paragraph("RUO Disclaimer", styles["Section"]))
    story.append(Paragraph(_clean(claims.get("ruo_disclaimer") or ledger.get("ruo_disclaimer")), styles["BodyText"]))

    def _footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#56616f"))
        canvas.drawString(1.4 * cm, 0.65 * cm, "OmicsTrust CellAudit - Research Use Only")
        canvas.drawRightString(A4[0] - 1.4 * cm, 0.65 * cm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def _kv_table(rows: list[tuple[str, Any]], styles: Any) -> Any:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Table

    data = [[Paragraph(_clean(k), styles["Cell"]), Paragraph(_clean(v), styles["Cell"])] for k, v in rows]
    table = Table(data, colWidths=[4.3 * cm, 11.5 * cm])
    table.setStyle(_table_style(header=False))
    return table


def _bullet_list(items: list[Any], styles: Any) -> list[Any]:
    from reportlab.platypus import Paragraph, Spacer

    flowables: list[Any] = []
    for item in items:
        flowables.append(Paragraph(f"- {_clean(item)}", styles["BodyText"]))
        flowables.append(Spacer(1, 2))
    if not flowables:
        flowables.append(Paragraph("- none", styles["BodyText"]))
    return flowables


def _p(value: Any, styles: Any) -> Any:
    from reportlab.platypus import Paragraph

    return Paragraph(_clean(value), styles["Cell"])


def _table_style(header: bool):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8dee8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#11263c")),
        ])
    return TableStyle(commands)


def _clean(value: Any) -> str:
    if value is None:
        return "not available"
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _humanize(value: Any) -> str:
    if value is None:
        return "not available"
    return str(value).replace("_", " ")
