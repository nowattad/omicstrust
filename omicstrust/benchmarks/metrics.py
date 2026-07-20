from __future__ import annotations

import time

import numpy as np

from omicstrust.utils.memory import peak_memory_mb


def principal_angles(U_true, U_est):
    q1, _ = np.linalg.qr(np.asarray(U_true, dtype=float))
    q2, _ = np.linalg.qr(np.asarray(U_est, dtype=float))
    singular = np.linalg.svd(q1.T @ q2, compute_uv=False)
    singular = np.clip(singular, -1.0, 1.0)
    return np.arccos(singular)


def subspace_alignment(U_true, U_est) -> float:
    angles = principal_angles(U_true, U_est)
    if angles.size == 0:
        return 0.0
    return float(np.mean(np.cos(angles) ** 2))


def reconstruction_error(X, X_hat) -> float:
    X = np.asarray(X, dtype=float)
    X_hat = np.asarray(X_hat, dtype=float)
    denom = float(np.linalg.norm(X) + 1e-12)
    return float(np.linalg.norm(X - X_hat) / denom)


def auroc_score(y_true, scores):
    try:
        from sklearn.metrics import roc_auc_score

        if len(set(y_true)) < 2:
            return {"value": None, "warning": "AUROC requires at least two label classes."}
        return {"value": float(roc_auc_score(y_true, scores)), "warning": None}
    except Exception as exc:
        return {"value": None, "warning": str(exc)}


def average_precision_score(y_true, scores):
    try:
        from sklearn.metrics import average_precision_score as ap

        if len(set(y_true)) < 2:
            return {"value": None, "warning": "Average precision requires at least two label classes."}
        return {"value": float(ap(y_true, scores)), "warning": None}
    except Exception as exc:
        return {"value": None, "warning": str(exc)}


def false_positive_rate(y_true, y_pred) -> float:
    y_true = np.asarray(y_true).astype(bool)
    y_pred = np.asarray(y_pred).astype(bool)
    negatives = ~y_true
    denom = max(int(negatives.sum()), 1)
    return float(np.sum(y_pred & negatives) / denom)


def explained_variance_ratio(eigenvalues):
    values = np.maximum(np.asarray(eigenvalues, dtype=float), 0.0)
    total = float(values.sum())
    return values / total if total > 0 else np.zeros_like(values)


def calibration_error(expected, observed) -> float:
    return float(np.mean(np.abs(np.asarray(expected, dtype=float) - np.asarray(observed, dtype=float))))


def runtime_seconds(start, end=None) -> float:
    return float((time.perf_counter() if end is None else end) - start)


__all__ = [
    "principal_angles",
    "subspace_alignment",
    "reconstruction_error",
    "auroc_score",
    "average_precision_score",
    "false_positive_rate",
    "explained_variance_ratio",
    "calibration_error",
    "runtime_seconds",
    "peak_memory_mb",
]
