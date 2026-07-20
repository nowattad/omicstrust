# PC11 Confirmatory Analysis Contract

This contract separates computational reproducibility within VANISH from true
external validation.

## Discovery Specification

- Outcome: 28-day mortality
- Treatment contrast: vasopressin versus noradrenaline
- Base interaction model:
  `death ~ vasopressor * PC + steroid + SRS + age + APACHE II + sex`
- Candidate family: 25 transcriptomic principal components
- Multiple-testing control: Benjamini-Hochberg across screened components
- Robustness checks: label permutation, patient bootstrap, metadata-explanation
  model, SRS-interaction challenges, and major-comorbidity adjustment

## Confirmatory Re-analysis Within VANISH

A team independently re-analyzing E-MTAB-7581 must lock the eligible sample
set, preprocessing, normalization, variable-feature selection, PCA convention,
covariate encoding, missing-data handling, model formula, random seeds,
permutation count, bootstrap count, and success criteria before inspecting the
interaction result.

Because PCA component order and sign can change, a reconstructed component must
be matched to the original PC11 using prespecified loading-concordance and sign
orientation rules. Selecting whichever reconstructed component has the smallest
interaction p-value is discovery, not confirmation.

## External Validation

External validation requires a separate compatible cohort containing baseline
transcriptomics, vasopressin/noradrenaline exposure, outcome labels, and enough
clinical and technical metadata to apply a locked axis specification without
re-optimizing it.

Possible conclusions are `reproduced`, `not_reproduced`, or `inconclusive`.
None of these outcomes alone establishes clinical utility.

Research Use Only.
