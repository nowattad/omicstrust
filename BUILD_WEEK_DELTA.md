# OmicsTrust Build Week Delta

This document distinguishes the research prototype that existed before OpenAI
Build Week from the product work completed during the July 13-21, 2026 build
period. It is intended to make the judged contribution explicit and auditable.

## Before Build Week

The project already contained a deterministic omics audit engine, command-line
workflows, research scripts, and the retrospective VANISH PC11/VasoGate result.
Those foundations established the scientific problem and supplied a real case
study, but they did not yet form a focused judge-ready product.

## Built And Hardened During Build Week

- Focused the release on one promise: audit whether an omics result is
  interpretable before expensive validation.
- Added the optional GPT-5.6 Evidence Copilot for natural-language intent
  interpretation and evidence explanation.
- Added privacy-preserving AI payload construction with `store=False`; raw
  matrices, patient rows, and local paths remain local.
- Implemented a central workflow registry and made explicit workflow selection
  authoritative. An explicit workflow can no longer be silently rerouted.
- Restored and polished the private local Web console.
- Added a dedicated, conservative PC11 evidence view with the preserved report,
  machine-readable statistics, checksum, and claim boundary.
- Improved normalized Copilot results, failure hierarchy, metadata
  conservatism, and clear `safe`, `limited`, `unsafe`, and `needs_validation`
  decisions.
- Hardened public metadata retrieval against SSRF, unsafe URL schemes, private
  network targets, oversized responses, and unsafe XML parsing.
- Removed unrelated drug-design product surfaces from the focused release.
- Added and repaired regression, routing, privacy, security, API, report, and
  metadata-conservatism tests.
- Built a complete English demo video package with captions and reproducible
  source assets.

## Verification Snapshot

Verified on July 20, 2026:

```text
119 passed, 7 skipped, 3 warnings
```

The skipped tests require a private/raw VANISH fixture that is intentionally
not distributed. The warnings are one dependency deprecation warning and two
expected duplicate-feature-name warnings in conservatism tests.

## GPT-5.6 Responsibility Boundary

GPT-5.6 may interpret a research question, help complete structured workflow
inputs, and explain a compact deterministic result. It does not calculate the
scientific statistics, alter trust decisions, override an explicit workflow,
or make clinical recommendations.

## Evidence Boundary

The VANISH PC11/VasoGate result is a retrospective internal research signal.
It is preserved as a real integration case, not presented as an externally
validated biomarker, a causal conclusion, or a treatment-selection rule.

Research Use Only. Not for diagnosis, prognosis, treatment selection, dosing,
or clinical decision-making.
