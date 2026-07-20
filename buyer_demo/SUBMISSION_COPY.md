# OmicsTrust Submission Copy

## One Line

OmicsTrust is a GPT-5.6-assisted, deterministic evidence-audit platform that
tests whether an omics result is reproducible, confounded, metadata-limited, or
safe to carry into external validation.

## What We Built

Researchers can upload or point to an omics dataset, choose metadata fields, and
receive a conservative trust verdict with an HTML/PDF report, failure hierarchy,
claim matrix, reproducibility record, and evidence ledger. GPT-5.6 converts
natural-language research intent into a registered workflow and explains the
deterministic output without receiving raw matrices or changing statistics.

## Why It Is Different

Most analysis tools optimize for producing a result. OmicsTrust is optimized for
knowing when the result must not be interpreted. Missing metadata becomes unknown
risk, confounding can veto a stable signal, and post-hoc discovery remains
separate from locked validation.

## Proof Case

The preserved VANISH case recovered a retrospective PC11/vasopressor interaction
with multiple-testing correction, permutation support, bootstrap stability, and
an explicit refusal to claim clinical utility before independent validation.

## OpenAI Use

- Model: `gpt-5.6` through the Responses API.
- Structured output for intent and evidence interpretation.
- Explicit workflows cannot be silently rerouted.
- Deterministic statistics are immutable.
- Raw expression matrices and patient rows remain local.
- The product remains fully functional when the AI layer is disabled.

## Boundary

Research Use Only. No diagnosis, treatment recommendation, dosing, clinical
decision support, or regulatory-readiness claim.
