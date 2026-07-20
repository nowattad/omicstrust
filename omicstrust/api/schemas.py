from __future__ import annotations

from dataclasses import dataclass
from typing import Any


try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - API dependency is optional.
    BaseModel = None
    Field = None


if BaseModel is not None:

    class AuditPathRequest(BaseModel):
        data_path: str
        output_dir: str | None = None
        batch_key: str | None = None
        donor_key: str | None = None
        label_key: str | None = None
        config_path: str | None = None
        background: bool = Field(default=False, description="Run in a background task when true.")

    class InspectPathRequest(BaseModel):
        data_path: str

else:

    @dataclass
    class AuditPathRequest:
        data_path: str
        output_dir: str | None = None
        batch_key: str | None = None
        donor_key: str | None = None
        label_key: str | None = None
        config_path: str | None = None
        background: bool = False

        def model_dump(self) -> dict[str, Any]:
            return self.__dict__.copy()

    @dataclass
    class InspectPathRequest:
        data_path: str

        def model_dump(self) -> dict[str, Any]:
            return self.__dict__.copy()
