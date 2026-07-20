# OmicsTrust

OmicsTrust is a Research Use Only evidence-audit platform for omics results.
It answers one question:

> Is this molecular signal stable, reproducible, and sufficiently protected
> from metadata and technical failure modes to support interpretation?

The deterministic engine audits data quality, structural signal, empirical
null calibration, batch and donor risk, technical confounding, resampling
stability, multiple testing, reproducibility, and claim boundaries. It returns
a conservative decision: `safe`, `limited`, `unsafe`, or `needs_validation`.

## Evidence Copilot

Evidence Copilot is an optional GPT-5.6 layer around the deterministic engine.
It translates a natural-language research question into a registered workflow
and explains the completed evidence package.

GPT-5.6 does not calculate statistics, choose an explicit workflow over the
user, alter audit results, or make clinical decisions. OmicsTrust sends only
the question, user-supplied field names, and a compact deterministic result
summary. Expression matrices and patient rows remain local.

```text
research question
      |
      v
GPT-5.6 intent interpretation (optional)
      |
      v
validated workflow registry
      |
      v
deterministic OmicsTrust engine
      |
      +--> trust decision + failure hierarchy
      +--> claim matrix + evidence ledger
      +--> HTML/PDF/JSON report
      |
      v
GPT-5.6 evidence explanation (optional, non-authoritative)
```

## Preserved Proof: VANISH PC11 / VasoGate

The primary case study is a retrospective treatment-response discovery in the
VANISH septic shock transcriptomic cohort. OmicsTrust screened 25 principal
components and identified PC11 as the strongest internal candidate interaction
with vasopressin versus noradrenaline allocation and 28-day mortality.

Reported internal evidence includes:

- 116 analyzed patients and 28,220 expression features
- interaction OR per 1 SD PC11: 0.16881
- Wald p: 0.00377
- likelihood-ratio p: 0.001258
- Benjamini-Hochberg FDR: 0.03145
- permutation p: 0.003996
- bootstrap negative-direction stability: 99.9%
- metadata explanation R2: 0.01793

The preserved report, machine-readable result, analysis contract, and checksum
are in [`case_studies/vanish_pc11`](case_studies/vanish_pc11). This is a strong
internal research signal, not an externally validated biomarker or treatment
rule.

## Build Week Release

This submission focuses OmicsTrust into one product: a private evidence-audit
console for researchers deciding whether an omics result is interpretable.

- [`BUILD_WEEK_DELTA.md`](BUILD_WEEK_DELTA.md) separates the pre-existing
  research engine from the work completed during Build Week.
- [`JUDGE_GUIDE.md`](JUDGE_GUIDE.md) provides a short, reproducible evaluation
  path for the Web, CLI, API, GPT-5.6, and PC11 evidence surfaces.
- The focused release is verified by 119 passing automated tests. Seven
  VANISH-fixture tests are skipped because private/raw cohort data are not
  distributed in this public repository.

## Install

```bash
python -m pip install -e ".[dev,api,reports,ai]"
```

`OPENAI_API_KEY` is optional. Without it, every deterministic CLI, Web, API,
audit, discovery, and validation workflow remains available.

## Two-Minute Demo

Start the private local console:

```bash
omicstrust serve --host 127.0.0.1 --port 8765 --results-root results/platform
```

Open `http://127.0.0.1:8765` and select **PC11 Evidence** to inspect the
preserved report. Select **Evidence Copilot** to route a research question into
an audit workflow.

Run a deterministic synthetic audit:

```bash
python examples/generate_synthetic_h5ad.py --output examples/synthetic.h5ad
omicstrust audit examples/synthetic.h5ad \
  --batch-key batch \
  --label-key signal_label \
  --output results/synthetic_audit
```

Run the optional GPT-5.6 Copilot over the same deterministic workflow:

```bash
OPENAI_API_KEY="..." omicstrust copilot \
  "Audit whether batch structure limits biological interpretation." \
  --data examples/synthetic.h5ad \
  --batch-key batch \
  --label-key signal_label \
  --output results/copilot_demo
```

## Core Workflows

- `audit`: complete trust audit for `.h5ad`, `.csv`, `.tsv`, or text matrices
- `inspect`: input shape, columns, layers, and metadata suggestions
- `validate`: schema and data-quality gate
- `copilot`: GPT-5.6 intent and evidence layer with deterministic fallback
- `de_novo_treatment_response_discovery`: generic RUO latent-axis interaction screen
- `lock-axis`: freeze an axis and validation contract
- `validate-axis`: test a locked axis on a separate dataset
- `benchmark` and `benchmark-real`: controlled and real-data comparisons
- `reproduce`: verify inputs, environment, and output provenance

## Outputs

Each audit can produce:

- `report.html` and `report.pdf`
- `summary.json` and `trust_report.json`
- `failure_report.json`
- `claim_matrix.json`
- `evidence_ledger.json`
- metrics, figures, configuration, environment, seeds, and fingerprints

## Privacy And Safety

- Local/private deployment is the default.
- API token protection is available for private deployments.
- Public metadata search does not download large expression matrices.
- GPT-5.6 integration uses `store=False` and excludes expression matrices and
  patient rows from the request payload.
- Explicit workflow selection cannot be silently rerouted.
- Clinical, diagnostic, dosing, and patient-level treatment requests are rejected.

## Claim Boundary

OmicsTrust audits evidence; it does not certify biological truth. A stable
statistical component can still be unsafe to interpret when metadata are
missing, batch or donor structure dominates, technical covariates explain the
signal, or external validation is absent.

Research Use Only. Not for diagnosis, prognosis, treatment selection, dosing,
or clinical decision-making.
