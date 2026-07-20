# Failure Modes

- `no_signal_above_null`: No component exceeds the configured empirical-null threshold.
- `batch_dominated_signal`: A major component is more associated with batch/donor than with the biological label.
- `donor_dominated_signal`: Donor identity dominates the fitted structure.
- `technical_covariate_dominance`: Library size, detected genes, mitochondrial percentage, or related covariates explain major structure.
- `unstable_subspace`: Bootstrap resampling produces substantially different subspaces.
- `unstable_rank`: Selected rank changes substantially across resamples.
- `null_miscalibration`: Null behavior is anti-conservative or otherwise not reliable.
- `insufficient_null_permutations`: Too few permutations support reliable empirical thresholds.
- `high_dropout_failure`: Dropout/zero inflation is high enough to weaken interpretation.
- `high_sparsity_warning`: Matrix sparsity is high enough to warrant caution.
- `low_sample_size_failure`: Too few cells are available for stable inference.
- `label_leakage_risk`: Labels are strongly confounded with technical covariates.
- `preprocessing_sensitive_result`: Results depend strongly on preprocessing choices.
- `overcorrection_risk`: Correction removes plausible label-associated structure.
- `baseline_outperforms_primary_method`: A baseline method gives stronger or more stable audit evidence.
- `non_reproducible_environment`: Package versions or input fingerprints differ from the recorded run.
- `memory_risk`: The requested operation risks unsafe dense conversion or memory exhaustion.
- `missing_metadata_warning`: Required metadata is missing or incomplete.
