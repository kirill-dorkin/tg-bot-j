from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator


def counter(name: str, **labels: str) -> None:
    # Placeholder for Prometheus counter
    return


@contextmanager
def timer(name: str, **labels: str) -> Iterator[None]:
    _ = time.time()
    try:
        yield
    finally:
        _ = time.time()

