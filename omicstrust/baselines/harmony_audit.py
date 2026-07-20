def audit_harmony_embedding(embedding, obs=None, batch_key=None):
    if embedding is None:
        raise NotImplementedError("Harmony audit mode requires a supplied embedding; correction is not part of core.")
    return {"method": "Harmony audit", "n_cells": len(embedding), "batch_key": batch_key}
