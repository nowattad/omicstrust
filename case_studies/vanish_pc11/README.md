# VANISH PC11 / VasoGate Case Study

This directory preserves the primary OmicsTrust treatment-response discovery
case study. It is part of the core product story and must not be interpreted as
a clinical biomarker or treatment recommendation.

## Research Question

Can a transcriptomic axis modify the association between randomized
vasopressin versus noradrenaline allocation and 28-day mortality in the VANISH
septic shock transcriptomic cohort?

## Preserved Result

- Dataset: VANISH / E-MTAB-7581 whole-blood transcriptomics
- Eligible patients analyzed: 116
- Expression features: 28,220
- Variable features used for discovery: 5,000
- Principal components screened: 25
- Top candidate: PC11
- Interaction: `C(vasopressor)[T.Vasopressin]:PC11`
- Beta: -1.77897
- Odds ratio per 1 SD: 0.16881
- Wald p: 0.00377
- Likelihood-ratio p: 0.001258
- Benjamini-Hochberg FDR: 0.03145
- Permutation p: 0.003996
- Bootstrap negative-direction stability: 0.999
- Metadata explanation R2: 0.01793

## Evidence Files

- `evidence/OmicsTrust_VANISH_PC11_Vasopressin_Response_Axis_Report.pdf`
  is the preserved 12-page research report supplied for this case study.
- `discovery_summary.json` is a machine-readable snapshot of the reported
  statistics and claim boundary.
- `ANALYSIS_CONTRACT.md` records the discovery model and the conditions needed
  for a valid confirmatory re-analysis.
- `SHA256SUMS.txt` records fingerprints for the report, summary, and analysis
  contract.

The canonical discovery executor remains in
`omicstrust/workflows/de_novo_treatment_response.py`. The VANISH integration
script remains in `scripts/vanish_denovo_vasopressin_endotype_discovery.py`.

The supporting research chain is also preserved:

- `scripts/vanish_pc11_independence_challenge.py`
- `scripts/vanish_pc11_mechanism_screen_v7.py`
- `scripts/vanish_pdia6_independence_bootstrap_v8.py`
- `scripts/vanish_pdia6_specificity_screen_v9.py`
- `scripts/make_steroid_safety_gate_evidence_pack.py`
- `scripts/vanish_pc11_annotate_from_illumina_manifest_v2.py`

## Claim Boundary

The result supports a retrospective, internally robust, research-stage
treatment-response hypothesis within VANISH. It does not establish clinical
utility, a diagnostic threshold, causal mechanism, treatment guidance, or
external validation. A locked specification and an independent compatible
cohort are required before the claim can be strengthened.

Research Use Only. Not for clinical decision-making.
