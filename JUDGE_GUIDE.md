# OmicsTrust Judge Guide

This guide provides a short path through the working product. OmicsTrust runs
locally so private omics matrices and patient-level rows do not need to leave
the evaluator's machine.

## 1. Install

Python 3.10 or later is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,api,reports,ai]"
```

## 2. Launch The Web Console

```bash
omicstrust serve --host 127.0.0.1 --port 8765 --results-root results/platform
```

Open <http://127.0.0.1:8765>.

Recommended path:

1. Open **Audit** to inspect the deterministic workflow.
2. Open **Evidence Copilot** to see the registered-workflow and GPT-5.6 safety
   boundary.
3. Open **PC11 Evidence** to inspect the preserved real research case and its
   explicit claim limitations.

`OPENAI_API_KEY` is optional. Without it, the deterministic engine and Copilot
fallback remain fully usable. With it, GPT-5.6 can interpret intent and explain
the completed deterministic evidence.

## 3. Run A Reproducible Audit

```bash
python examples/generate_synthetic_h5ad.py --output examples/synthetic.h5ad
omicstrust audit examples/synthetic.h5ad \
  --batch-key batch \
  --label-key signal_label \
  --output results/synthetic_audit
omicstrust reproduce results/synthetic_audit
```

Inspect:

- `results/synthetic_audit/report.html`
- `results/synthetic_audit/trust_report.json`
- `results/synthetic_audit/failure_report.json`
- `results/synthetic_audit/claim_matrix.json`
- `results/synthetic_audit/evidence_ledger.json`

## 4. Run Evidence Copilot

```bash
OPENAI_API_KEY="..." omicstrust copilot \
  "Audit whether batch structure limits biological interpretation." \
  --data examples/synthetic.h5ad \
  --batch-key batch \
  --label-key signal_label \
  --output results/copilot_demo
```

The AI explanation is non-authoritative. The deterministic result, failure
hierarchy, and claim matrix remain authoritative.

## 5. Run Tests

```bash
pytest -q
```

Expected public-repository result:

```text
119 passed, 7 skipped
```

The skipped tests require a VANISH fixture that is not distributed. No raw
VANISH patient-level data are included in this repository.

## Safety Boundary

Research Use Only. OmicsTrust is not a diagnostic, prognostic, treatment,
dosing, or clinical decision-support system.
