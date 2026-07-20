from __future__ import annotations

from typing import Any, Protocol, TypeAlias

import numpy as np


class SparseLike(Protocol):
    shape: tuple[int, int]
    data: np.ndarray

    def sum(self, axis: int | None = None) -> Any: ...


MatrixLike: TypeAlias = np.ndarray | SparseLike
