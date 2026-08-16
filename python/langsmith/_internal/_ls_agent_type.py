"""Shared primitives for the ``ls_agent_type`` metadata tag.

Consumed by wrappers/integrations that stamp or inspect ``ls_agent_type`` on
traced runs (``wrap_openai``, OpenAI Agents SDK processor, future wrappers).
Keep this module SDK-agnostic: the caller passes in the parent run tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from langsmith.run_trees import RunTree

LsAgentType = Literal["root", "middleware", "subagent", "compaction"]

# Non-root tags: preserved against default/structural stamping.
NON_ROOT_LS_AGENT_TYPES: frozenset[str] = frozenset(
    {"middleware", "subagent", "compaction"}
)


def resolve_default_ls_agent_type(
    parent_runtree: Optional[RunTree],
) -> Optional[str]:
    """Return ``"root"`` at trace root, ``None`` when nested.

    Nested runs rely on ``traceable``'s ``outer_metadata`` propagation to carry
    the trace-root's tag down; this function intentionally emits nothing so
    that propagation is not overwritten.
    """
    return "root" if parent_runtree is None else None


def apply_default_ls_agent_type(
    metadata: dict,
    parent_runtree: Optional[RunTree],
) -> None:
    """Stamp default ``ls_agent_type`` on ``metadata`` if the key is absent."""
    if "ls_agent_type" in metadata:
        return
    tag = resolve_default_ls_agent_type(parent_runtree)
    if tag is not None:
        metadata["ls_agent_type"] = tag
