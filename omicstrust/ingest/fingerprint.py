from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from omicstrust.utils.validation import is_sparse_matrix


def fingerprint_input(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_matrix(X: Any) -> str:
    digest = hashlib.sha256()
    digest.update(str(tuple(X.shape)).encode("utf-8"))
    if is_sparse_matrix(X):
        X_csr = X.tocsr()
        digest.update(np.asarray(X_csr.data).tobytes())
        digest.update(np.asarray(X_csr.indices).tobytes())
        digest.update(np.asarray(X_csr.indptr).tobytes())
    else:
        digest.update(np.ascontiguousarray(np.asarray(X)).tobytes())
    return digest.hexdigest()
