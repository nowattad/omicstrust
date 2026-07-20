from __future__ import annotations


def require_scanpy():
    try:
        import scanpy as sc

        return sc
    except Exception as exc:
        raise NotImplementedError(
            "Scanpy-compatible preprocessing is optional and requires installing scanpy."
        ) from exc
