from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from omicstrust.ingest.anndata_loader import load_dataset, load_matrix_table


def load_matrix(source: str | Path | Any, obs: pd.DataFrame | None = None, var: pd.DataFrame | None = None):
    return load_dataset(source, obs=obs, var=var)


__all__ = ["load_matrix", "load_matrix_table"]
