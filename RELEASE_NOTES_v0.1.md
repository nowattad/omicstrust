# OmicsTrust v0.1 Build Week Release Notes

Status: Research Use Only

## Product

OmicsTrust is a local-first omics evidence-audit platform. It tests whether an
apparent result is supported, reproducible, confounded, metadata-limited, or
unsafe to interpret. It produces a conservative trust verdict, failure
hierarchy, claim matrix, report, and evidence ledger.

This release has one product message:

> Send us your omics result. We audit whether the evidence is interpretable.

## Release Scope

- CLI, Web, REST API, upload, and local-path audit workflows.
- Structural signal and empirical-null assessment.
- Batch, donor, label, and technical-covariate risk assessment.
- Separation of statistical stability from biological interpretability.
- Conservative missing-metadata and duplicate-feature handling.
- HTML, PDF, JSON, reviewer report, failure report, claim matrix, and evidence
  ledger outputs.
- Locked-axis validation and generic RUO treatment-response discovery contracts.
- Optional GPT-5.6 Evidence Copilot through the Responses API.
- One preserved proof case: VANISH PC11 / VasoGate.

MoleculeTrust and drug/compound-generation material are not part of this release.
The OmicsTrust statistical engine and PC11 discovery evidence remain intact.

## GPT-5.6 Contract

GPT-5.6 may interpret a natural-language research request and explain a completed
deterministic result. It cannot override an explicit workflow, alter statistics,
make a clinical recommendation, or see raw expression matrices and patient rows.
Local paths and row-level identifiers are redacted. Responses use structured
output, `store=false`, and a hashed safety identifier.

Without `OPENAI_API_KEY`, all deterministic functionality remains available.

## Preserved PC11 Evidence

- `case_studies/vanish_pc11/discovery_summary.json`
- `case_studies/vanish_pc11/ANALYSIS_CONTRACT.md`
- `case_studies/vanish_pc11/evidence/OmicsTrust_VANISH_PC11_Vasopressin_Response_Axis_Report.pdf`
- `case_studies/vanish_pc11/SHA256SUMS.txt`

The report PDF SHA-256 is:

```text
a6f913630d083b02b2079dadb37a99e310623bb8cdb8a72841e1d56944a13411
```

PC11 remains a strong internal retrospective research signal, not an externally
validated biomarker or treatment-selection rule.

## Two-Minute Demo

```bash
cd /path/to/omicstrust
./buyer_demo/demo_commands.sh
```

Open `http://127.0.0.1:8765`, then show **Audit**, **Evidence Copilot**, and
**PC11 Evidence**. The spoken script is in
`buyer_demo/DEMO_SCRIPT_2_MINUTES.md`.

## Verification

```text
119 passed, 7 skipped, 3 warnings
```

The seven skipped tests require the removed raw VANISH fixture. The preserved
report and discovery-summary API endpoints are tested directly. The warnings are
one dependency deprecation warning and deliberate duplicate-variable-name
warnings used to test conservative handling.

Manual verification also completed:

- CLI synthetic audit completed with `batch_dominated_signal`, `unsafe`, and
  `safe_to_interpret: no`.
- Web local-path audit completed and exposed HTML/PDF/JSON/ledger links.
- Embedded report figures are served from traversal-safe job artifact paths.
- Desktop and 390px mobile layouts were inspected with no horizontal overflow.
- Audit, Evidence Copilot, and PC11 Evidence tabs were exercised.
- Browser console reported no errors.
- Preserved PC11 PDF rendered cleanly and its API endpoint returned valid PDF.
- A clean Wheel was built with the PC11 report included and unrelated security
  lab packages excluded.

The OpenAI request contract is covered by mocked Responses API tests. A live
GPT-5.6 call requires the deployer's `OPENAI_API_KEY` and was not required for
the deterministic release gates.

## Claim Boundary

OmicsTrust is not a diagnostic, treatment recommendation, dosing system,
clinical decision-support product, biomarker qualification package, or FDA
submission. Independent external validation is required before stronger claims.
