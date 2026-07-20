from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def write_html_report(path: str | Path, context: dict[str, Any]) -> None:
    try:
        from jinja2 import Template
    except Exception:
        Template = None

    model = _build_model(context)
    template_text = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OmicsTrust CellAudit Report</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #142033;
      --muted: #5b6676;
      --line: #d9e1ea;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --good: #176b4d;
      --warn: #8a5a00;
      --bad: #a32929;
      --accent: #245b7a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.48;
    }
    header {
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 28px 32px 22px;
    }
    main { max-width: 1180px; margin: 0 auto; padding: 24px 28px 48px; }
    h1 { margin: 0; font-size: 28px; font-weight: 760; letter-spacing: 0; }
    h2 { margin: 28px 0 12px; font-size: 18px; letter-spacing: 0; }
    h3 { margin: 16px 0 8px; font-size: 15px; letter-spacing: 0; }
    p { margin: 0 0 10px; }
    .subtitle { color: var(--muted); max-width: 820px; margin-top: 8px; }
    .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
    .button {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 7px 11px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--ink);
      text-decoration: none;
      background: #ffffff;
      font-size: 13px;
      font-weight: 620;
    }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .metric-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    .metric-value { font-size: 18px; font-weight: 760; margin-top: 6px; overflow-wrap: anywhere; }
    .status-good { color: var(--good); }
    .status-warn { color: var(--warn); }
    .status-bad { color: var(--bad); }
    .section-band { background: #ffffff; border: 1px solid var(--line); border-radius: 8px; padding: 18px; }
    table { border-collapse: collapse; width: 100%; background: #ffffff; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    th, td { border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; }
    th { background: #eef3f7; color: #25354a; font-weight: 720; }
    tr:last-child td { border-bottom: 0; }
    .failure { border-left: 4px solid var(--bad); }
    .claim-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
    ul { margin: 8px 0 0 18px; padding: 0; }
    li { margin: 5px 0; }
    img { display: block; max-width: 100%; border: 1px solid var(--line); border-radius: 6px; background: #ffffff; }
    code { background: #eef3f7; border: 1px solid var(--line); border-radius: 4px; padding: 1px 4px; }
    footer { color: var(--muted); font-size: 12px; margin-top: 28px; padding-top: 18px; border-top: 1px solid var(--line); }
  </style>
</head>
<body>
  <header>
    <h1>OmicsTrust / CellAudit Report</h1>
    <p class="subtitle">Scientific trust audit for omics data. The report separates statistical structure from confounding risk, metadata sufficiency, stability, and reproducibility.</p>
    <div class="toolbar">
      <a class="button" href="summary.json">JSON Summary</a>
      <a class="button" href="reviewer_report.md">Reviewer Report</a>
      <a class="button" href="report.pdf">PDF Report</a>
      <a class="button" href="evidence_ledger.json">Evidence Ledger</a>
    </div>
  </header>
  <main>
    <section class="grid">
      {% for metric in summary_cards %}
      <div class="panel">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value {{ metric.status_class }}">{{ metric.value }}</div>
      </div>
      {% endfor %}
    </section>

    <h2>Executive Recommendation</h2>
    <section class="section-band">
      <p><strong>Main failure:</strong> {{ main_failure }}</p>
      <p>{{ recommendation }}</p>
    </section>

    <h2>What Can And Cannot Be Claimed</h2>
    <section class="claim-list">
      <div class="panel">
        <h3>Can Claim</h3>
        <ul>{% for item in claim_matrix.can_claim %}<li>{{ item }}</li>{% endfor %}</ul>
      </div>
      <div class="panel">
        <h3>Cannot Claim</h3>
        <ul>{% for item in claim_matrix.cannot_claim %}<li>{{ item }}</li>{% endfor %}</ul>
      </div>
    </section>

    <h2>Failure Hierarchy</h2>
    {% if failures %}
    <table>
      <tr><th>Failure</th><th>Severity</th><th>Interpretation</th><th>Recommendation</th></tr>
      {% for failure in failures %}
      <tr class="failure"><td>{{ failure.failure_type }}</td><td>{{ failure.severity }}</td><td>{{ failure.interpretation }}</td><td>{{ failure.recommendation }}</td></tr>
      {% endfor %}
    </table>
    {% else %}
    <section class="section-band"><p>No configured failure modes were detected.</p></section>
    {% endif %}

    <h2>Audit Evidence</h2>
    <table>
      <tr><th>Area</th><th>Evidence</th></tr>
      {% for row in evidence_rows %}
      <tr><td>{{ row.area }}</td><td>{{ row.evidence }}</td></tr>
      {% endfor %}
    </table>

    <h2>Baseline Comparison</h2>
    <table>
      <tr><th>Method</th><th>Signal Score</th><th>Batch Risk</th><th>Runtime Seconds</th><th>Notes</th></tr>
      {% for row in baseline_rows %}
      <tr><td>{{ row.method }}</td><td>{{ row.signal_score }}</td><td>{{ row.batch_risk }}</td><td>{{ row.runtime_seconds }}</td><td>{{ row.warning }}</td></tr>
      {% endfor %}
    </table>

    <h2>Artifacts</h2>
    <table>
      <tr><th>Artifact</th><th>Path</th></tr>
      {% for artifact in artifacts %}
      <tr><td>{{ artifact.name }}</td><td><code>{{ artifact.path }}</code></td></tr>
      {% endfor %}
    </table>

    <h2>Figures</h2>
    {% for fig in figures %}
      <h3>{{ fig.title }}</h3>
      <img src="{{ fig.path }}" alt="{{ fig.title }}">
    {% endfor %}

    <footer>{{ ruo }}</footer>
  </main>
</body>
</html>
"""
    if Template is not None:
        html = Template(template_text).render(**model)
    else:
        html = "<html><body><h1>OmicsTrust / CellAudit Report</h1><pre>" + escape(str(model)) + "</pre></body></html>"
    Path(path).write_text(html, encoding="utf-8")


def _build_model(context: dict[str, Any]) -> dict[str, Any]:
    summary = context.get("summary", {})
    trust = context.get("trust_report", {})
    batch = context.get("batch_risk_report", {})
    null_report = context.get("null_report", {})
    stability = context.get("stability_report", {})
    qc = context.get("qc_report", {})
    evidence = context.get("evidence_ledger", {})
    claim_matrix = context.get("claim_matrix", {})
    component_artifacts = context.get("component_artifacts", {})
    failures = [_clean_dict(f) for f in context.get("failure_report", {}).get("failures", [])]
    baseline_rows = [_clean_dict(row) for row in context.get("benchmark_rows", [])]

    summary_cards = [
        _card("Data QC", summary.get("data_qc")),
        _card("Structural Signal", summary.get("structural_signal")),
        _card("Empirical Null", summary.get("empirical_null")),
        _card("Batch Risk", summary.get("batch_risk")),
        _card("Stability", summary.get("stability")),
        _card("Trust Level", summary.get("trust_level")),
        _card("Trust Score", trust.get("trust_score")),
        _card("Safe To Interpret", summary.get("safe_to_interpret")),
    ]
    evidence_rows = [
        {"area": "Input", "evidence": _input_fingerprint_label(evidence.get("input_fingerprints", {}))},
        {"area": "QC", "evidence": f"cells={_fmt(qc.get('n_cells'))}; features={_fmt(qc.get('n_features'))}; zero_fraction={_fmt(qc.get('zero_fraction'))}"},
        {"area": "Signal", "evidence": f"score={_fmt(context.get('signal_report', {}).get('signal_score'))}; selected_rank={_fmt(context.get('signal_report', {}).get('selected_rank'))}"},
        {"area": "Null", "evidence": f"method={_fmt(null_report.get('method'))}; n_permutations={_fmt(null_report.get('n_permutations'))}; calibration={_fmt(null_report.get('calibration_status'))}"},
        {"area": "Batch/Donor", "evidence": f"overall={_fmt(batch.get('overall_risk'))}; donor={_fmt(batch.get('donor_risk'))}; max_batch_r2={_fmt(batch.get('max_batch_r2'))}"},
        {"area": "Stability", "evidence": f"status={_fmt(stability.get('stability_status'))}; mean_subspace_similarity={_fmt(stability.get('mean_subspace_similarity'))}"},
        {"area": "Reproducibility", "evidence": _fmt(evidence.get("reproducibility_status"))},
    ]
    artifacts = [{"name": key.replace("_", " ").title(), "path": value} for key, value in component_artifacts.items() if isinstance(value, str)]
    return {
        "summary_cards": summary_cards,
        "main_failure": _fmt(summary.get("main_failure") or "none"),
        "recommendation": _fmt(summary.get("recommendation")),
        "claim_matrix": {
            "can_claim": [_fmt(v) for v in claim_matrix.get("can_claim", [])],
            "cannot_claim": [_fmt(v) for v in claim_matrix.get("cannot_claim", [])],
        },
        "failures": failures,
        "evidence_rows": evidence_rows,
        "baseline_rows": baseline_rows,
        "artifacts": artifacts,
        "figures": context.get("figures", []),
        "ruo": _fmt(claim_matrix.get("ruo_disclaimer") or evidence.get("ruo_disclaimer") or "Research Use Only."),
    }


def _card(label: str, value: Any) -> dict[str, str]:
    text = _fmt(value)
    lowered = text.lower()
    status_class = "status-good"
    if lowered in {"high", "fail", "unsafe", "no", "not_passed", "insufficient_information"} or "unsafe" in lowered:
        status_class = "status-bad"
    elif lowered in {"warning", "moderate", "unknown", "not_assessable", "limited"} or "warning" in lowered:
        status_class = "status-warn"
    return {"label": label, "value": text, "status_class": status_class}


def _clean_dict(row: dict[str, Any]) -> dict[str, str]:
    return {str(key): _fmt(value) for key, value in row.items()}


def _input_fingerprint_label(fingerprints: dict[str, Any]) -> str:
    if not fingerprints:
        return "not available"
    labels = []
    for path, value in fingerprints.items():
        digest = value.get("sha256") if isinstance(value, dict) else value
        labels.append(f"{path}: {str(digest)[:12]}")
    return "; ".join(labels)


def _fmt(value: Any) -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, list):
        return ", ".join(_fmt(v) for v in value) if value else "none"
    if isinstance(value, dict):
        return ", ".join(f"{k}={_fmt(v)}" for k, v in value.items()) if value else "none"
    return escape(str(value))
