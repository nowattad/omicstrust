from __future__ import annotations

import numpy as np


def spectra_equal_with_tolerance(left, right, atol: float = 1e-8) -> bool:
    return bool(np.allclose(np.asarray(left), np.asarray(right), atol=atol, rtol=0))
