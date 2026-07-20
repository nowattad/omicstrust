from __future__ import annotations

from omicstrust.audit import run_audit


if __name__ == "__main__":
    run_audit(
        "examples/synthetic.h5ad",
        batch_key="batch",
        label_key="signal_label",
        output="results/synthetic_audit",
    )
