from __future__ import annotations

from pathlib import Path

import pandas as pd


def import_multiqc_summary(path: str | Path) -> pd.DataFrame:
    """Import a MultiQC summary table.

    MultiQC schemas vary by tool. This function intentionally returns a table
    without pretending to harmonize every possible field.
    """

    path = Path(path)
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    return pd.read_csv(path, sep=sep)
