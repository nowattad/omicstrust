def overcorrection_warning(before_label_r2: float, after_label_r2: float, drop_threshold: float = 0.5) -> dict:
    if before_label_r2 <= 0:
        return {"risk": "unknown", "relative_drop": 0.0}
    relative_drop = max(0.0, (before_label_r2 - after_label_r2) / before_label_r2)
    return {"risk": "high" if relative_drop >= drop_threshold else "low", "relative_drop": relative_drop}
