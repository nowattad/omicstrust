# Reproducibility Protocol

Every audit captures environment metadata, package versions, command history, random seeds, input fingerprints, and the effective config.

Run:

```bash
omicstrust reproduce results/study_001
```

The reproduce command checks input fingerprints and package versions against the recorded provenance. If exact reproduction is impossible, it records the reason in `reproducibility_report.json`.
