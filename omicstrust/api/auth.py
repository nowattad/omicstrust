from __future__ import annotations

import os
from secrets import compare_digest
from typing import Any


TOKEN_ENV_VAR = "OMICSTRUST_API_TOKEN"


class AuthConfig:
    def __init__(self, token: str | None = None):
        self.token = token if token is not None else os.environ.get(TOKEN_ENV_VAR)

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def verify_request(self, request: Any) -> bool:
        if not self.enabled:
            return True
        supplied = request.headers.get("x-omicstrust-token")
        if not supplied:
            authorization = request.headers.get("authorization", "")
            prefix = "Bearer "
            if authorization.startswith(prefix):
                supplied = authorization[len(prefix) :]
        if not supplied:
            supplied = request.cookies.get("omicstrust_token")
        return bool(supplied and compare_digest(str(supplied), str(self.token)))
