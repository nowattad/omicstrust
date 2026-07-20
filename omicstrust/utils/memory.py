from __future__ import annotations

import os
import resource


def peak_memory_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if os.uname().sysname == "Darwin":
        return float(usage / (1024 * 1024))
    return float(usage / 1024)
