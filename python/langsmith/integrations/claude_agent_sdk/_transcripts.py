"""Post-conversation transcript reconciliation.

After a conversation ends this module:

1. Creates LLM runs for subagent turns that were not relayed through
   the parent stream (the SDK only streams the first assistant message
   per subagent; subsequent turns are folded into the Agent tool result).

2. Patches accurate token usage onto all LLM runs from the JSONL
   transcripts (the live stream only has partial streaming counts).

.. note::

   The transcript JSONL format is **not a contracted API** of the Claude
   Agent SDK.  Changes to the format could silently degrade trace
   fidelity.  If the SDK begins relaying all subagent messages through
   the stream, step 1 becomes a no-op (the dedup guard skips already-
   seen ``message_id`` values).
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from ._hooks import SessionState, _current_session_or_default
from ._usage import (
    extract_usage_metadata,
    read_llm_turns_from_transcript,
    read_usage_from_transcript,
)

if TYPE_CHECKING:
    from ._client import TurnLifecycle

logger = logging.getLogger(__name__)

LLM_RUN_NAME = "claude.assistant.turn"


def reconcile_from_transcripts(
    tracker: "TurnLifecycle",
    session: Optional[SessionState] = None,
) -> None:
    """Read transcripts and reconcile LLM runs.

    This function does two things after the conversation ends:

    1. **Missing subagent LLM runs** — creates LLM runs for subagent
       turns whose ``message_id`` is not already in
       ``tracker.llm_runs_by_message_id``.

    2. **Usage correction** — patches accurate usage from the JSONL
       transcripts onto all LLM runs (both streamed and synthetic).

    If *session* is omitted the current ContextVar-bound session (or the
    module-level default) is used. The caller in ``receive_response``
    passes the per-conversation session explicitly to stay safe under
    concurrent tracing.
    """
    if session is None:
        session = _current_session_or_default()
    _create_missing_subagent_llm_runs(tracker, session)
    _patch_usage_on_llm_runs(tracker, session)


# ── Step 1: synthetic subagent LLM runs ─────────────────────────────


def _create_missing_subagent_llm_runs(
    tracker: "TurnLifecycle",
    session: SessionState,
) -> None:
    # Guard against the same message_id being processed twice (e.g. if
    # the same transcript path appears multiple times in the list).
    created: set[str] = set()
    for path, subagent_run in session.subagent_transcript_paths:
        try:
            turns = read_llm_turns_from_transcript(path)
            for turn in turns:
                mid = turn["message_id"]
                if mid in tracker.llm_runs_by_message_id:
                    continue
                if mid in created:
                    continue

                ts = _parse_timestamp(turn.get("timestamp"))

                input_messages = turn.get("input_messages", [])
                llm_metadata: dict[str, Any] = {
                    "ls_provider": "anthropic",
                }
                if turn.get("model"):
                    llm_metadata["ls_model_name"] = turn["model"]

                llm_run = subagent_run.create_child(
                    name=LLM_RUN_NAME,
                    run_type="llm",
                    inputs={"messages": input_messages} if input_messages else {},
                    extra={"metadata": llm_metadata},
                    start_time=ts,
                )

                llm_run.outputs = {
                    "content": turn.get("content", []),
                    "role": "assistant",
                }

                raw_usage = turn.get("usage")
                if raw_usage:
                    usage_meta = extract_usage_metadata(raw_usage)
                    if usage_meta:
                        meta = llm_run.extra.setdefault("metadata", {})
                        meta["usage_metadata"] = usage_meta

                llm_run.end(end_time=ts)
                try:
                    llm_run.post()
                    llm_run.patch()
                except Exception as e:
                    logger.warning(f"Failed to post/patch subagent LLM run: {e}")

                tracker.llm_runs_by_message_id[mid] = llm_run
                created.add(mid)
                logger.debug(f"Created missing subagent LLM run for message {mid}")
        except Exception as e:
            logger.warning(
                f"Failed to create subagent LLM runs from {path}: {e}",
                exc_info=True,
            )


# ── Step 2: usage patching ──────────────────────────────────────────


def _patch_usage_on_llm_runs(
    tracker: "TurnLifecycle",
    session: SessionState,
) -> None:
    if not tracker.llm_runs_by_message_id:
        return

    all_usage: dict[str, dict[str, Any]] = {}

    main_path = session.main_transcript_path
    if main_path:
        all_usage.update(read_usage_from_transcript(main_path))

    for path, _run in session.subagent_transcript_paths:
        all_usage.update(read_usage_from_transcript(path))

    patched = 0
    for message_id, run in tracker.llm_runs_by_message_id.items():
        usage = all_usage.get(message_id)
        if usage:
            meta = run.extra.setdefault("metadata", {})
            meta["usage_metadata"] = usage
            patched += 1

    if patched:
        logger.debug(f"Set usage on {patched} LLM run(s) from transcripts")


# ── Helpers ─────────────────────────────────────────────────────────


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
