# Contributing

Contributions should preserve conservative scientific framing, deterministic numerical behavior, sparse-aware memory safety, and explicit failure-mode reporting.

Run tests before submitting changes:

```bash
pytest -q
```

New numerical methods should include tests for determinism, shape, missing metadata handling, and NaN/Inf safety.
