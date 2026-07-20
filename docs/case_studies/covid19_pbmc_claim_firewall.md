# OmicsTrust Case Study: COVID-19 PBMC Claim Firewall

## Dataset

Public COVID-19 PBMC single-cell data downloaded as H5AD.

## Audit question

Can a COVID/Healthy signal in PBMC data be safely interpreted as a biomarker-like omics claim?

## Whole-PBMC audit

The whole-PBMC audit used:

- label: `Status`
- donor: `Donor_full`
- confounding stress key: `cell_type_coarse`

OmicsTrust found high overall risk. Dominant components were explained primarily by cell-type composition and donor structure rather than disease status.

Decision:

`no_safe_biomarker_claim_found`

## CD14 monocyte follow-up

To reduce cell-type composition confounding, OmicsTrust repeated the audit inside CD14 monocytes only.

The disease-status signal became more visible, but the leading component remained unsafe to interpret because metadata/donor-associated structure explained more variance than Status.

Decision:

`no_safe_biomarker_claim_found`

## Interpretation

OmicsTrust did not claim that no COVID biology exists. It found that the available evidence does not support a safe biomarker claim from this audit setting.

## Claim boundary

Can claim:

- OmicsTrust audited a real public COVID-19 PBMC single-cell dataset.
- OmicsTrust detected strong composition and donor/confounding risk.
- OmicsTrust blocked unsafe biomarker interpretation and issued a conservative RUO certificate.

Cannot claim:

- OmicsTrust discovered or validated a COVID biomarker.
- OmicsTrust supports diagnosis, treatment selection, or patient management.
- The absence of a safe claim means absence of biology.

## RUO disclaimer

Research Use Only. Not for clinical diagnosis, treatment guidance, or patient management.

## Cell-type-stratified follow-up

OmicsTrust then audited individual cell-type subsets using:

- label: `Status`
- donor: `Donor_full`
- confounding stress key: `Sex`

### Results

| Cell type | Audit summary | Certificate decision |
|---|---|---|
| B cells | Structural signal detected, empirical null passed, batch risk high, trust unsafe, safe_to_interpret no | `no_safe_biomarker_claim_found` |
| CD14 monocytes | Structural signal detected, empirical null passed, batch risk high, trust unsafe, safe_to_interpret no | `no_safe_biomarker_claim_found` |
| CD4 T cells | Structural signal detected, empirical null passed, batch risk high, trust unsafe, safe_to_interpret no | `no_safe_biomarker_claim_found` |
| NK cells | Structural signal detected, empirical null passed, batch risk high, trust unsafe, safe_to_interpret no | `no_safe_biomarker_claim_found` |
| CD8 T cells | Structural signal detected, empirical null passed, batch risk moderate, stability high, trust moderate, safe_to_interpret yes | `insufficient_evidence_for_biomarker_claim` |

## Key finding

OmicsTrust did not reject every signal. It separated unsafe signals from a more interpretable CD8 T-cell research signal. The CD8 T-cell signal was not escalated to a biomarker claim because locked external validation was not available.

## Product interpretation

This case study demonstrates OmicsTrust as a claim-boundary engine:

- unsafe/confounded signals are blocked;
- more interpretable RUO signals are allowed to remain research candidates;
- biomarker escalation is blocked until locked external validation exists.
