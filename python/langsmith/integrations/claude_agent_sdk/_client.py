"""Client instrumentation for Claude Agent SDK."""

import logging
import time
import weakref
from collections.abc import AsyncGenerator, AsyncIterable
from datetime import datetime, timezone
from functools import cache
from typing import Any, Optional

from langsmith._internal import _context
from langsmith.run_helpers import get_current_run_tree, trace

from ._config import get_tracing_config
from ._hooks import (
    SessionState,
    _current_session,
    _register_session,
    _set_session_root,
    _unregister_session,
    clear_active_tool_runs,
    get_subagent_run_by_tool_id,
    post_tool_use_failure_hook,
    post_tool_use_hook,
    pre_tool_use_hook,
    subagent_start_hook,
    subagent_stop_hook,
)
from ._messages import (
    build_llm_input,
    flatten_content_blocks,
    unwrap_message_dicts,
)
from ._tools import (
    clear_parent_run_tree,
    get_parent_run_tree,
    set_parent_run_tree,
)
from ._transcripts import LLM_RUN_NAME, reconcile_from_transcripts
from ._usage import extract_usage_metadata

logger = logging.getLogger(__name__)

TRACE_CHAIN_NAME = "claude.conversation"


@cache
def _get_package_version(package_name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


class TurnLifecycle:
    """Track ongoing model runs so consecutive messages are recorded correctly.

    The Claude Agent SDK may deliver a single assistant turn as multiple
    ``AssistantMessage`` events (e.g. one with ``ThinkingBlock``, another
    with ``TextBlock``/``ToolUseBlock``).  Messages that share the same
    ``message_id`` are accumulated into a single LLM run.
    """

    def __init__(self, query_start_time: Optional[float] = None):
        self.current_run: Optional[Any] = None
        self.current_message_id: Optional[str] = None
        self.next_start_time: Optional[float] = query_start_time
        # message_id → RunTree for all LLM runs created this conversation.
        # Used to retroactively set usage from transcripts.
        self.llm_runs_by_message_id: dict[str, Any] = {}
        # Runs that have been end()ed but not yet patch()ed.
        # Deferred so transcript usage can be set before the single patch().
        self._pending_patch: list[Any] = []

    def start_llm_run(
        self,
        message: Any,
        prompt: Any,
        history: list[dict[str, Any]],
        parent: Optional[Any] = None,
    ) -> Optional[dict[str, Any]]:
        """Begin or continue a model run for *message*.

        If *message* has the same ``message_id`` as the current run the
        output is appended; otherwise a new run is started (ending any
        previous one first).
        """
        message_id = getattr(message, "message_id", None)
        start = self.next_start_time or time.time()

        # Same turn – just accumulate the output blocks and update usage.
        # Return None so the caller does NOT append a duplicate history
        # entry; the original entry in ``history`` is updated in place.
        if message_id and message_id == self.current_message_id and self.current_run:
            content = flatten_content_blocks(getattr(message, "content", None))
            if content and self.current_run.outputs:
                prev = self.current_run.outputs.get("content", [])
                if isinstance(prev, list) and isinstance(content, list):
                    merged = prev + content
                    self.current_run.outputs["content"] = merged
                    # Update the existing history entry in place so
                    # subsequent LLM runs see a single merged message.
                    for entry in reversed(history):
                        if entry.get("role") == "assistant":
                            entry["content"] = merged
                            break
                elif isinstance(content, list):
                    self.current_run.outputs["content"] = content
            self._set_usage_from_message(message, self.current_run)
            return None

        # Different turn – end previous but defer patch() until
        # transcript usage is available.
        if self.current_run:
            self.current_run.end()
            self._pending_patch.append(self.current_run)

        final_output, run = begin_llm_run_from_assistant_messages(
            [message], prompt, history, start_time=start, parent=parent
        )
        self.current_run = run
        self.current_message_id = message_id
        self.next_start_time = None

        if run:
            if message_id:
                self.llm_runs_by_message_id[message_id] = run
            self._set_usage_from_message(message, run)

        return final_output

    @staticmethod
    def _set_usage_from_message(message: Any, run: Any) -> None:
        """Set usage metadata on a run from a live AssistantMessage.

        Always overwrites — later chunks in the same turn have more
        accurate counts.  Transcript-based usage will overwrite again
        if available.
        """
        raw_usage = getattr(message, "usage", None)
        if not raw_usage:
            return
        usage_meta = extract_usage_metadata(raw_usage)
        if usage_meta:
            meta = run.extra.setdefault("metadata", {})
            meta["usage_metadata"] = usage_meta

    def mark_next_start(self) -> None:
        """Mark when the next assistant message will start."""
        self.next_start_time = time.time()

    def close(self) -> None:
        """End any open run and add to pending patch list."""
        if self.current_run:
            self.current_run.end()
            self._pending_patch.append(self.current_run)
            self.current_run = None

    def flush(self) -> None:
        """Patch all deferred LLM runs. Call after usage has been set."""
        for run in self._pending_patch:
            try:
                run.patch()
            except Exception as e:
                logger.warning(f"Failed to patch LLM run: {e}")
        self._pending_patch.clear()


def begin_llm_run_from_assistant_messages(
    messages: list[Any],
    prompt: Any,
    history: list[dict[str, Any]],
    start_time: Optional[float] = None,
    parent: Optional[Any] = None,
) -> tuple[Optional[dict[str, Any]], Optional[Any]]:
    """Create a traced model run from assistant messages."""
    if not messages or type(messages[-1]).__name__ != "AssistantMessage":
        return None, None

    last_msg = messages[-1]
    model = getattr(last_msg, "model", None)
    if parent is None:
        parent = get_parent_run_tree() or get_current_run_tree()
    if not parent:
        return None, None

    inputs = build_llm_input(prompt, history)
    outputs = [
        {"content": flatten_content_blocks(m.content), "role": "assistant"}
        for m in messages
        if hasattr(m, "content")
    ]

    llm_metadata: dict[str, Any] = {"ls_provider": "anthropic"}
    if model:
        llm_metadata["ls_model_name"] = model

    llm_run = parent.create_child(
        name=LLM_RUN_NAME,
        run_type="llm",
        inputs={"messages": inputs} if inputs else {},
        extra={"metadata": llm_metadata},
        start_time=datetime.fromtimestamp(start_time, tz=timezone.utc)
        if start_time
        else None,
    )

    try:
        llm_run.post()
    except Exception as e:
        logger.warning(f"Failed to post LLM run: {e}")

    # Set outputs after posting so they are sent with end_time on the patch.
    llm_run.outputs = outputs[-1] if len(outputs) == 1 else {"content": outputs}

    final_content = (
        {"content": flatten_content_blocks(last_msg.content), "role": "assistant"}
        if hasattr(last_msg, "content")
        else None
    )
    return final_content, llm_run


def _bind_hook_to_session(hook: Any, session: Optional[SessionState]) -> Any:
    """Return a hook callable that runs with *session* bound, if provided."""
    if session is None:
        return hook

    async def _bound(input_data: Any, tool_use_id: Any, context: Any) -> Any:
        token = _current_session.set(session)
        try:
            return await hook(input_data, tool_use_id, context)
        finally:
            _current_session.reset(token)

    return _bound


def _inject_tracing_hooks(options: Any, session: Optional[SessionState] = None) -> None:
    """Inject LangSmith tracing hooks into ClaudeAgentOptions.

    If *session* is provided, injected hook callables bind that session around
    each hook invocation. This is important because the Claude SDK may execute
    hooks in async contexts that do not inherit the ``receive_response``
    ContextVar; binding at hook injection time keeps each client isolated.
    """
    if not hasattr(options, "hooks"):
        return

    # Initialize hooks dict if not present
    if options.hooks is None:
        options.hooks = {}

    for event in (
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "SubagentStart",
        "SubagentStop",
    ):
        if event not in options.hooks:
            options.hooks[event] = []

    try:
        from claude_agent_sdk import HookMatcher  # type: ignore[import-not-found]

        langsmith_pre_matcher = HookMatcher(
            matcher=None, hooks=[_bind_hook_to_session(pre_tool_use_hook, session)]
        )
        langsmith_post_matcher = HookMatcher(
            matcher=None, hooks=[_bind_hook_to_session(post_tool_use_hook, session)]
        )
        langsmith_failure_matcher = HookMatcher(
            matcher=None,
            hooks=[_bind_hook_to_session(post_tool_use_failure_hook, session)],
        )
        langsmith_subagent_start_matcher = HookMatcher(
            matcher=None, hooks=[_bind_hook_to_session(subagent_start_hook, session)]
        )
        langsmith_subagent_stop_matcher = HookMatcher(
            matcher=None, hooks=[_bind_hook_to_session(subagent_stop_hook, session)]
        )

        options.hooks["PreToolUse"].insert(0, langsmith_pre_matcher)
        options.hooks["PostToolUse"].insert(0, langsmith_post_matcher)
        options.hooks["PostToolUseFailure"].insert(0, langsmith_failure_matcher)
        options.hooks["SubagentStart"].insert(0, langsmith_subagent_start_matcher)
        options.hooks["SubagentStop"].insert(0, langsmith_subagent_stop_matcher)

        logger.debug("Injected LangSmith tracing hooks into ClaudeAgentOptions")
    except ImportError:
        logger.warning("Failed to import HookMatcher from claude_agent_sdk")
    except Exception as e:
        logger.warning(f"Failed to inject tracing hooks: {e}")


def _wrap_tool_handler(
    original_handler: Any,
    session: Optional[SessionState] = None,
    tool_name: Optional[str] = None,
) -> Any:
    """Wrap an MCP tool handler to propagate LangSmith run context.

    The Claude SDK runs hooks and tool handlers in different async task
    contexts, so contextvars set in ``PreToolUse`` are invisible to the
    handler. This wrapper copies the active tool run into the contextvar before
    calling the original handler, so ``@traceable`` calls inside the handler
    nest correctly.
    """

    async def _wrapped(args: Any) -> Any:
        # The most recently added active tool run is the one PreToolUse just
        # created for this invocation. Prefer an explicitly bound client
        # session because tool handlers may run in an async context that did
        # not inherit _current_session.
        tool_run = _get_last_active_tool_run(session, args=args, tool_name=tool_name)
        if tool_run:
            token = _context._PARENT_RUN_TREE_REF.set(weakref.ref(tool_run))
            session_token = (
                _current_session.set(session) if session is not None else None
            )
            try:
                return await original_handler(args)
            finally:
                if session_token is not None:
                    _current_session.reset(session_token)
                _context._PARENT_RUN_TREE_REF.reset(token)
        return await original_handler(args)

    _wrapped._langsmith_wrapped = True  # type: ignore[attr-defined]
    _wrapped._langsmith_original_handler = original_handler  # type: ignore[attr-defined]
    _wrapped._langsmith_session = session  # type: ignore[attr-defined]
    _wrapped._langsmith_tool_name = tool_name  # type: ignore[attr-defined]
    return _wrapped


def _tool_run_matches(run: Any, args: Any, tool_name: Optional[str]) -> bool:
    """Return whether *run* appears to be for this SDK MCP handler call.

    Matching is intentionally strict: we require both the tool name and the
    handler args to line up with what the ``PreToolUse`` hook recorded. This
    avoids cross-attributing a handler invocation to the wrong client's active
    tool run under concurrency.
    """
    if not tool_name:
        return False
    run_name = str(getattr(run, "name", ""))
    # SDK MCP tools show up in hook data as e.g. ``mcp__weather__get_weather``
    # while the handler only knows its short name ``get_weather``.
    name_matches = (
        tool_name == run_name or tool_name in run_name or run_name in tool_name
    )
    if not name_matches:
        return False
    inputs = getattr(run, "inputs", None)
    if not isinstance(inputs, dict):
        return False
    # PreToolUse stores {} when the tool had no inputs, otherwise
    # {"input": <tool_input>}. Normalise both sides before comparing.
    recorded = inputs.get("input", {}) if inputs else {}
    return recorded == (args or {})


def _newest_matching_tool_run(
    sessions: list[SessionState], args: Any, tool_name: Optional[str]
) -> Any:
    """Return the most recently created active tool run that matches."""
    candidates: list[tuple[float, Any]] = []
    for candidate_session in sessions:
        for run, start_time in candidate_session.active_tool_runs.values():
            if _tool_run_matches(run, args, tool_name):
                candidates.append((start_time, run))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _get_last_active_tool_run(
    session: Optional[SessionState] = None,
    *,
    args: Any = None,
    tool_name: Optional[str] = None,
) -> Any:
    """Return the active tool run for an SDK MCP handler, or None.

    Lookup order:

    1. The session explicitly bound to the handler (if any).
    2. The session bound to the current ContextVar.
    3. The module-level default session (unit tests / unbound callers).
    4. Any live client session — only used when the handler is unbound and the
       SDK invoked it in a detached async context. Requires an exact tool
       name + args match to avoid cross-attribution across clients.
    """
    from ._hooks import (
        _current_session,
        _current_session_or_default,
        _registered_sessions,
    )

    # If we have a specific session (explicitly bound, current-context, or the
    # test default), just return its newest active tool run. There is no
    # cross-client ambiguity at that point.
    def _newest_in(s: SessionState) -> Any:
        if not s.active_tool_runs:
            return None
        latest_id = max(
            s.active_tool_runs,
            key=lambda tid: s.active_tool_runs[tid][1],
        )
        return s.active_tool_runs[latest_id][0]

    if session is not None:
        return _newest_in(session)

    current_session = _current_session.get()
    if current_session is not None:
        run = _newest_in(current_session)
        if run is not None:
            return run

    default_session = _current_session_or_default()
    if default_session is not current_session:
        run = _newest_in(default_session)
        if run is not None:
            return run

    # Last resort: the SDK invoked this handler in a detached async context and
    # the handler object wasn't bound to a session. Require strict tool-name +
    # args match so concurrent clients can't steal each other's attribution.
    return _newest_matching_tool_run(_registered_sessions(), args, tool_name)


def instrument_claude_client(original_class: Any) -> None:
    """Patch ``ClaudeSDKClient`` **in place** to trace calls.

    In-place patching (rather than subclassing + reference replacement)
    ensures that callers who imported ``ClaudeSDKClient`` *before*
    ``configure_claude_agent_sdk()`` was called still get instrumented.
    """
    if getattr(original_class, "_langsmith_instrumented", False):
        return  # Already wrapped, avoid double-tracing

    # ── stash originals ──────────────────────────────────────────────
    _orig_init = original_class.__init__
    _orig_query = original_class.query
    _orig_receive_response = original_class.receive_response

    # ── patched __init__ ─────────────────────────────────────────────
    def _traced_init(self: Any, *args: Any, **kwargs: Any) -> None:
        options = kwargs.get("options") or (args[0] if args else None)
        self._ls_session = SessionState()
        if options:
            _inject_tracing_hooks(options, self._ls_session)
        _orig_init(self, *args, **kwargs)
        self._ls_prompt = None
        self._ls_start_time = None
        self._ls_streamed_input = None

    # ── patched query ────────────────────────────────────────────────
    async def _traced_query(self: Any, *args: Any, **kwargs: Any) -> Any:
        self._ls_start_time = time.time()
        self._ls_streamed_input = None
        prompt = args[0] if args else kwargs.get("prompt")

        if prompt is None:
            pass
        elif isinstance(prompt, str):
            self._ls_prompt = prompt
        elif isinstance(prompt, AsyncIterable):
            collector: list[dict[str, Any]] = []
            self._ls_streamed_input = collector
            self._ls_prompt = None

            async def _gen_wrapper() -> AsyncGenerator[dict[str, Any], None]:
                async for msg in prompt:
                    collector.append(msg)
                    yield msg

            if args:
                args = (_gen_wrapper(),) + args[1:]
            else:
                kwargs["prompt"] = _gen_wrapper()
        else:
            self._ls_prompt = str(prompt)

        return await _orig_query(self, *args, **kwargs)

    # ── patched receive_response ─────────────────────────────────────
    async def _traced_receive_response(self: Any) -> AsyncGenerator[Any, None]:
        messages = _orig_receive_response(self)

        trace_inputs: dict[str, Any] = {}
        trace_metadata: dict[str, Any] = {
            "ls_integration": "claude-agent-sdk",
            "ls_integration_version": _get_package_version("claude_agent_sdk"),
        }

        awaiting_streamed_input = self._ls_streamed_input is not None

        if self._ls_prompt:
            trace_inputs["prompt"] = self._ls_prompt

        if hasattr(self, "options") and self.options:
            if hasattr(self.options, "system_prompt") and self.options.system_prompt:
                system_prompt = self.options.system_prompt
                if isinstance(system_prompt, str):
                    trace_inputs["system"] = system_prompt
                elif isinstance(system_prompt, dict):
                    if system_prompt.get("type") == "preset":
                        preset_text = (
                            f"preset: {system_prompt.get('preset', 'claude_code')}"
                        )
                        if "append" in system_prompt:
                            preset_text += f"\nappend: {system_prompt['append']}"
                        trace_inputs["system"] = preset_text
                    else:
                        trace_inputs["system"] = system_prompt

            for attr in ["model", "permission_mode", "max_turns"]:
                if hasattr(self.options, attr):
                    val = getattr(self.options, attr)
                    if val is not None:
                        trace_metadata[attr] = val

        config = get_tracing_config()
        user_metadata = config.get("metadata") or {}

        trace_kwargs: dict[str, Any] = {
            "name": config.get("name") or TRACE_CHAIN_NAME,
            "run_type": "chain",
            "inputs": trace_inputs,
            "metadata": {
                **trace_metadata,
                **user_metadata,
                "ls_agent_type": "root",
            },
        }
        if config.get("project_name"):
            trace_kwargs["project_name"] = config["project_name"]
        if config.get("tags"):
            trace_kwargs["tags"] = config["tags"]

        async with trace(**trace_kwargs) as run:
            # Bind this client's state container to the ContextVar so stream
            # helpers on this SDK event loop pick it up (see
            # _hooks.SessionState). This keeps concurrent ClaudeSDKClient
            # instances — eval runs, FastAPI handlers, Celery workers,
            # asyncio.gather — from corrupting each other's correlation state.
            session = getattr(self, "_ls_session", None)
            if session is None:
                session = self._ls_session = SessionState()
            session_token = _register_session(session)
            _set_session_root(session, run)
            parent_token = set_parent_run_tree(run)
            tracker = TurnLifecycle(self._ls_start_time)
            collected_by_ctx: dict[Optional[str], list[dict[str, Any]]] = {None: []}

            prompt_for_llm: Any = self._ls_prompt

            try:
                async for msg in messages:
                    if awaiting_streamed_input and self._ls_streamed_input:
                        unwrapped_messages = unwrap_message_dicts(
                            self._ls_streamed_input
                        )
                        if unwrapped_messages:
                            run.inputs["messages"] = unwrapped_messages
                            prompt_for_llm = self._ls_streamed_input
                        awaiting_streamed_input = False

                    msg_type = type(msg).__name__

                    if msg_type == "AssistantMessage":
                        parent_tool_use_id = getattr(msg, "parent_tool_use_id", None)
                        llm_parent = (
                            get_subagent_run_by_tool_id(parent_tool_use_id)
                            if parent_tool_use_id
                            else None
                        )

                        ctx_key = parent_tool_use_id
                        ctx_history = collected_by_ctx.setdefault(ctx_key, [])

                        content = tracker.start_llm_run(
                            msg,
                            prompt_for_llm if parent_tool_use_id is None else None,
                            ctx_history,
                            parent=llm_parent,
                        )
                        if content:
                            ctx_history.append(content)

                    elif msg_type == "UserMessage":
                        parent_tool_use_id = getattr(msg, "parent_tool_use_id", None)
                        ctx_key = parent_tool_use_id
                        ctx_history = collected_by_ctx.setdefault(ctx_key, [])

                        if hasattr(msg, "content"):
                            flattened = flatten_content_blocks(msg.content)
                            if (
                                isinstance(flattened, list)
                                and flattened
                                and isinstance(flattened[0], dict)
                                and flattened[0].get("type") == "tool_result"
                            ):
                                for block in flattened:
                                    tool_use_id = block.get("tool_use_id")
                                    ctx_history.append(
                                        {
                                            "role": "tool",
                                            "content": block.get("content", ""),
                                            "tool_call_id": tool_use_id,
                                        }
                                    )
                                    if (
                                        tool_use_id
                                        and tool_use_id in session.active_tool_runs
                                    ):
                                        tool_run, _ = session.active_tool_runs.pop(
                                            tool_use_id
                                        )
                                        result_content = block.get("content", "")
                                        is_error = block.get("is_error", False)
                                        tool_run.end(
                                            outputs={"output": result_content},
                                            error=str(result_content)
                                            if is_error
                                            else None,
                                        )
                                        try:
                                            tool_run.patch()
                                        except Exception as e:
                                            logger.warning(
                                                "Failed to patch"
                                                f" orphaned tool run: {e}"
                                            )
                            else:
                                ctx_history.append(
                                    {
                                        "content": flattened,
                                        "role": "user",
                                    }
                                )
                        tracker.mark_next_start()
                    elif msg_type == "ResultMessage":
                        meta = {
                            k: v
                            for k, v in {
                                "num_turns": getattr(msg, "num_turns", None),
                                "session_id": getattr(msg, "session_id", None),
                                "duration_ms": getattr(msg, "duration_ms", None),
                                "duration_api_ms": getattr(
                                    msg, "duration_api_ms", None
                                ),
                                "is_error": getattr(msg, "is_error", None),
                            }.items()
                            if v is not None
                        }
                        if meta:
                            run.metadata.update(meta)

                    yield msg
                main_collected = collected_by_ctx.get(None, [])
                run.end(outputs=main_collected[-1] if main_collected else None)
            except Exception:
                logger.exception("Error while tracing Claude Agent stream")
            finally:
                tracker.close()
                reconcile_from_transcripts(tracker, session=session)
                tracker.flush()
                clear_parent_run_tree(parent_token)
                try:
                    clear_active_tool_runs(session)
                finally:
                    _unregister_session(session, session_token)

    # ── apply patches to the class itself ────────────────────────────
    original_class.__init__ = _traced_init
    original_class.query = _traced_query
    original_class.receive_response = _traced_receive_response
    original_class._langsmith_instrumented = True


def instrument_sdk_mcp_tool(tool_class: Any) -> None:
    """Patch ``SdkMcpTool.__init__`` to auto-wrap handlers.

    Wrapping happens at construction time so that any tool created
    *after* ``configure_claude_agent_sdk()`` automatically gets
    run-context propagation, regardless of how ``tool`` or
    ``create_sdk_mcp_server`` were imported.
    """
    if getattr(tool_class, "_langsmith_handler_patched", False):
        return

    _orig_init = tool_class.__init__

    def _patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        _orig_init(self, *args, **kwargs)
        handler = self.handler
        if callable(handler) and not getattr(handler, "_langsmith_wrapped", False):
            self.handler = _wrap_tool_handler(
                handler, tool_name=getattr(self, "name", None)
            )

    tool_class.__init__ = _patched_init
    tool_class._langsmith_handler_patched = True
