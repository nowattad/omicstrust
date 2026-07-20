def audit_scvi_embedding(embedding, obs=None, batch_key=None):
    if embedding is None:
        raise NotImplementedError("scVI audit mode requires a supplied latent embedding; training is not part of core.")
    return {"method": "scVI audit", "n_cells": len(embedding), "batch_key": batch_key}
