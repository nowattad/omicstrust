# Assumptions

## Data Orientation

Matrices are cells by features. Rows are observations/cells and columns are genes/features.

## Empirical Nulls

Permutation nulls test whether observed structure is stronger than structure retained after the configured randomization. They do not prove biological causality.

## Batch Risk

Association between spectral scores and batch/donor/technical covariates is treated as interpretation risk. If batch association is high, CellAudit conservatively marks affected components as unsafe to interpret biologically.

## Stability

Bootstrap subspace similarity estimates whether fitted structure persists under cell resampling. Low stability is a failure mode even when a component is above the null.

## Trust Score

The trust score is an internal audit summary. It is not a probability of biological truth and should not be used as a standalone discovery claim.
