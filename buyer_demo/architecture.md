# OmicsTrust Architecture

```text
CLI / Web / REST API / Private deployment
                 |
                 v
       Deterministic workflow registry
                 |
       +---------+----------+
       |                    |
       v                    v
Evidence audit       Locked/discovery workflows
       |                    |
       +---------+----------+
                 v
 QC -> empirical null -> confounding -> stability -> trust gate
                 |
                 v
 Report + claim matrix + failure report + evidence ledger

Optional GPT-5.6 layer
  - interprets research intent and metadata field names
  - may suggest a registered workflow when none is explicit
  - explains deterministic output under the RUO claim boundary
  - never receives raw matrices or patient rows
  - never owns or changes a statistic
```

## Scientific Contract

The audit distinguishes mathematical signal from biological interpretability.
Missing batch, donor, or label metadata produce `unknown` risk and can block
safe interpretation. Absence of evidence is never converted into evidence of
safety.

Every run records input and configuration fingerprints, package versions,
random seeds, null diagnostics, warnings, failure hierarchy, trust decision,
and reproducibility state.

## Surfaces

- CLI: audit, inspect, validate, reproduce, lock-axis, validate-axis, Copilot.
- Web: one focused workspace for audit, Evidence Copilot, and PC11 evidence.
- REST API: local path/upload jobs, status, reports, ledgers, and case evidence.
- Deployment: localhost by default; token-protected private mode and Docker.
