# OmicsTrust Build Week Demo

## The Product

OmicsTrust is a local-first, Research Use Only evidence-audit platform for omics
results. A researcher supplies an omics dataset or an analysis question;
OmicsTrust tests whether the apparent signal is statistically supported,
stable, reproducible, confounded, metadata-limited, or unsafe to interpret.

The offer is deliberately narrow:

> Send us your omics result. We audit whether the evidence is interpretable.

## The Two-Minute Story

1. Open the Audit workspace and show the dataset, metadata, and private/local
   execution controls.
2. Open Evidence Copilot. GPT-5.6 turns a natural-language research question
   into a constrained OmicsTrust workflow and explains the deterministic result.
3. Open PC11 Evidence. Show the preserved 12-page report, exact statistics, and
   the boundary between a strong internal signal and an unvalidated clinical
   claim.

The deterministic engine owns every statistic and verdict. GPT-5.6 receives no
raw expression matrix or patient rows, cannot rewrite statistics, and cannot
override an explicitly selected workflow.

## Run It

```bash
./buyer_demo/demo_commands.sh
```

Then open `http://127.0.0.1:8765`.

To enable the optional GPT-5.6 layer:

```bash
export OPENAI_API_KEY="your-key"
```

Without a key, every deterministic CLI, Web, API, and upload workflow remains
usable.

## Preserved Evidence

- `case_studies/vanish_pc11/discovery_summary.json`
- `case_studies/vanish_pc11/ANALYSIS_CONTRACT.md`
- `case_studies/vanish_pc11/evidence/OmicsTrust_VANISH_PC11_Vasopressin_Response_Axis_Report.pdf`
- `case_studies/vanish_pc11/SHA256SUMS.txt`

Research Use Only. Not for diagnosis, treatment selection, dosing, or clinical
decision-making. Independent external validation is required.
