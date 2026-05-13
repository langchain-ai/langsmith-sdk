# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr
from .runner_context_enum import RunnerContextEnum
from .runnable_config_param import RunnableConfigParam

__all__ = ["PlaygroundExperimentStreamParams"]


class PlaygroundExperimentStreamParams(TypedDict, total=False):
    dataset_id: Required[str]

    manifest: Required[object]

    options: Required[RunnableConfigParam]
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

    project_name: Required[str]

    secrets: Required[Dict[str, str]]

    commit: Optional[str]

    dataset_splits: Optional[SequenceNotStr[str]]

    evaluator_rules: Optional[SequenceNotStr[str]]

    metadata: Optional[Dict[str, object]]

    owner: Optional[str]

    parallel_tool_calls: Optional[bool]

    repetitions: int

    repo_handle: Optional[str]

    repo_id: Optional[str]

    requests_per_second: Optional[int]

    run_id: Optional[str]

    runner_context: Optional[RunnerContextEnum]

    tool_choice: Optional[str]

    tools: Optional[Iterable[object]]

    use_or_fallback_to_workspace_secrets: bool
