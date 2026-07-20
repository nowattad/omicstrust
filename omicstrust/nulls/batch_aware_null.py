from __future__ import annotations

from omicstrust.nulls.empirical_null import EmpiricalNull


def within_batch_null(**kwargs) -> EmpiricalNull:
    return EmpiricalNull(method="within_batch_permutation", **kwargs)
