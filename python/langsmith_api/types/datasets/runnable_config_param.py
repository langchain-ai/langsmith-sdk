# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from typing_extensions import TypedDict

from ..._types import SequenceNotStr

__all__ = ["RunnableConfigParam"]


class RunnableConfigParam(TypedDict, total=False):
    """Configuration for a `Runnable`.

    !!! note Custom values

        The `TypedDict` has `total=False` set intentionally to:

        - Allow partial configs to be created and merged together via `merge_configs`
        - Support config propagation from parent to child runnables via
            `var_child_runnable_config` (a `ContextVar` that automatically passes
            config down the call stack without explicit parameter passing), where
            configs are merged rather than replaced

        !!! example

            ```python
            # Parent sets tags
            chain.invoke(input, config={"tags": ["parent"]})
            # Child automatically inherits and can add:
            # ensure_config({"tags": ["child"]}) -> {"tags": ["parent", "child"]}
            ```
    """

    callbacks: Union[Iterable[object], object, None]

    configurable: Dict[str, object]

    max_concurrency: Optional[int]

    metadata: Dict[str, object]

    recursion_limit: int

    run_id: Optional[str]

    run_name: str

    tags: SequenceNotStr[str]
