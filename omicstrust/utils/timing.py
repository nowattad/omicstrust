from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator


def now() -> float:
    return time.perf_counter()


def runtime_seconds(start: float, end: float | None = None) -> float:
    return float((time.perf_counter() if end is None else end) - start)


@contextmanager
def timer() -> Iterator[dict[str, float]]:
    state = {"start": now(), "seconds": 0.0}
    try:
        yield state
    finally:
        state["seconds"] = runtime_seconds(state["start"])
