from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class TracingBytesLimiter:
    """Bound concurrent trace work by serialized bytes."""

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("Tracing byte limit must be nonnegative")
        self.capacity = capacity
        self._available = capacity
        self._condition = threading.Condition()

    @contextmanager
    def limit(self, size: int) -> Iterator[None]:
        if size < 0:
            raise ValueError("Tracing batch size must be nonnegative")
        if self.capacity == 0:
            yield
            return

        weight = min(size, self.capacity)
        with self._condition:
            self._condition.wait_for(lambda: self._available >= weight)
            self._available -= weight
        try:
            yield
        finally:
            with self._condition:
                self._available += weight
                self._condition.notify_all()
