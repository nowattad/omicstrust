from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from omicstrust.utils.typing import MatrixLike


@dataclass
class OmicsDataset:
    """Internal cell-by-feature data container used by CellAudit."""

    X: MatrixLike
    obs: pd.DataFrame | None
    var: pd.DataFrame | None
    layers: dict[str, MatrixLike] | None
    metadata: dict[str, Any]
    source_path: str | None
    fingerprint: str | None

    @property
    def shape(self) -> tuple[int, int]:
        return tuple(self.X.shape)  # type: ignore[return-value]
