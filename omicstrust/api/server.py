from __future__ import annotations

from pathlib import Path

from omicstrust.api.auth import AuthConfig
from omicstrust.api.jobs import JobStore


def create_app(*, results_root: str | Path = "results/platform", private_mode: bool = True, api_token: str | None = None):
    try:
        from fastapi import FastAPI
    except Exception as exc:
        raise NotImplementedError("The API layer is optional and requires fastapi.") from exc

    from omicstrust.api.routes import register_routes

    app = FastAPI(
        title="OmicsTrust Private Audit API",
        description="Local-first OmicsTrust API for private omics trust audits.",
        version="0.1.0",
    )
    register_routes(app, job_store=JobStore(results_root), private_mode=private_mode, auth=AuthConfig(api_token))
    return app
