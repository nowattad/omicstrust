from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from typing import Any


def capture_environment() -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
    }


def capture_package_versions(packages: list[str] | None = None) -> dict[str, str | None]:
    packages = packages or [
        "omicstrust",
        "numpy",
        "scipy",
        "pandas",
        "scikit-learn",
        "anndata",
        "pyyaml",
        "typer",
        "jinja2",
        "matplotlib",
        "psutil",
    ]
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return versions
