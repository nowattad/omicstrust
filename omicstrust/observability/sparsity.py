from __future__ import annotations

from omicstrust.utils.validation import matrix_nnz


def zero_fraction(X) -> float:
    return float(1.0 - matrix_nnz(X) / max(1, X.shape[0] * X.shape[1]))
