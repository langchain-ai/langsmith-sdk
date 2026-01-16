from typing import Any, Optional


class AnyInt(int):
    def __init__(self, low: Optional[int] = None, high: Optional[int] = None) -> None:
        """Integer with optional interval [low, high)."""
        super().__init__()
        self._low = low
        self._high = high

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, int):
            return False
        if self._low is not None and other < self._low:
            return False
        if self._high is not None and other >= self._high:
            return False
        return True
