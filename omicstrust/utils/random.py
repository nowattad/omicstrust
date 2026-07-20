from __future__ import annotations

import numpy as np


def rng_from_seed(random_state: int | None = 0) -> np.random.Generator:
    return np.random.default_rng(0 if random_state is None else int(random_state))


def stable_seed_sequence(seed: int, n: int) -> list[int]:
    root = np.random.SeedSequence(int(seed))
    return [int(s.generate_state(1)[0]) for s in root.spawn(n)]
