from __future__ import annotations

from omicstrust.nulls.empirical_null import EmpiricalNull


def label_shuffle_null(**kwargs) -> EmpiricalNull:
    return EmpiricalNull(method="label_shuffle", **kwargs)
