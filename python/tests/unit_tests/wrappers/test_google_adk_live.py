"""Unit tests for the Google ADK Live voice tracing integration.

Pure unit tests: they exercise ``LangSmithGoogleADKLivePlugin`` / ``_AdkLiveTracer`` /
``_LiveEventView`` without a network round-trip and without requiring the heavy
``google-adk`` install. Two seams make that possible:

* ``google.adk.plugins.base_plugin`` is stubbed into ``sys.modules`` before the
  plugin is imported when the real package is absent (mirrors how the
  livekit/pipecat processor tests stay framework-free). When ``google-adk`` is
  installed (CI), the real ``BasePlugin`` is used instead.
* ``start_session`` is patched to hand back ``MagicMock`` sessions, so no
  ``RunTree`` is created and nothing is posted to LangSmith. ``MagicMock``
  natively supports the context-manager protocol used by ``event_span``.

ADK events and invocation contexts are duck-typed (all-optional attributes read
via ``getattr``), so lightweight ``SimpleNamespace`` fakes stand in for them.
"""

import asyncio
import sys
import types
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _ensure_base_plugin() -> None:
    """Make ``google.adk.plugins.base_plugin.BasePlugin`` importable.

    No-op when the real package is installed; otherwise inject a minimal stub
    whose ``BasePlugin`` only accepts the ``name`` kwarg the plugin passes to
    ``super().__init__``.
    """
    try:
        import google.adk.plugins.base_plugin  # noqa: F401

        return
    except ModuleNotFoundError:
        pass

    adk = types.ModuleType("google.adk")
    plugins = types.ModuleType("google.adk.plugins")
    base = types.ModuleType("google.adk.plugins.base_plugin")

    class BasePlugin:
        def __init__(self, name):
            self.name = name

    base.BasePlugin = BasePlugin
    adk.plugins = plugins  # type: ignore[attr-defined]
    plugins.base_plugin = base  # type: ignore[attr-defined]
    sys.modules["google.adk"] = adk
    sys.modules["google.adk.plugins"] = plugins
    sys.modules["google.adk.plugins.base_plugin"] = base


_ensure_base_plugin()

from langsmith._internal._beta_decorator import (  # noqa: E402
    LangSmithBetaWarning,
    _warn_once,
)
from langsmith.integrations.google_adk_live import _plugin as adk_plugin  # noqa: E402
from langsmith.integrations.google_adk_live._plugin import (  # noqa: E402
    LangSmithGoogleADKLivePlugin,
    _LiveEventView,
    _usage_metadata,
)

# --------------------------------------------------------------------------- #
# Fakes for ADK event / invocation-context objects.
# --------------------------------------------------------------------------- #


def _txn(text, *, finished=False):
    """A fake transcription object (``.text`` / ``.finished``)."""
    return SimpleNamespace(text=text, finished=finished)


def _fcall(name, *, id=None, args=None):
    """A fake ``FunctionCall`` (``.name`` / ``.id`` / ``.args``)."""
    return SimpleNamespace(name=name, id=id, args=args)


def _fresp(name, *, id=None, response=None):
    """A fake ``FunctionResponse`` (``.name`` / ``.id`` / ``.response``)."""
    return SimpleNamespace(name=name, id=id, response=response)


def _part(*, audio=None, fcall=None, fresp=None):
    """A fake content part carrying at most one of audio / call / response."""
    return SimpleNamespace(
        inline_data=SimpleNamespace(data=audio) if audio is not None else None,
        function_call=fcall,
        function_response=fresp,
    )


def _event(
    *,
    parts=None,
    input_transcription=None,
    output_transcription=None,
    interrupted=False,
    turn_complete=False,
    usage_metadata=None,
):
    """A fake ADK ``run_live`` event with all-optional fields."""
    return SimpleNamespace(
        content=SimpleNamespace(parts=parts) if parts is not None else None,
        input_transcription=input_transcription,
        output_transcription=output_transcription,
        interrupted=interrupted,
        turn_complete=turn_complete,
        usage_metadata=usage_metadata,
    )


def _ctx(*, session_id=None, invocation_id=None):
    """A fake ADK ``InvocationContext``."""
    session = SimpleNamespace(id=session_id) if session_id is not None else None
    return SimpleNamespace(session=session, invocation_id=invocation_id)


def _run(coro):
    """Drive an async callback to completion (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


def _new_plugin(**kwargs):
    """Construct the plugin, silencing the one-shot beta warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LangSmithBetaWarning)
        return LangSmithGoogleADKLivePlugin(**kwargs)


@pytest.fixture
def make_plugin(monkeypatch):
    """Factory yielding a plugin whose ``start_session`` returns mock sessions.

    Returns ``(factory, created)`` where ``created`` accumulates the ``MagicMock``
    session returned for each ``before_run_callback``, so a test can assert which
    session received which calls.
    """
    created = []

    def fake_start_session(**_kwargs):
        session = MagicMock(name=f"session-{len(created)}")
        session.now.return_value = 1.23
        created.append(session)
        return session

    monkeypatch.setattr(adk_plugin, "start_session", fake_start_session)

    return _new_plugin, created


# --------------------------------------------------------------------------- #
# _LiveEventView — event field inspection.
# --------------------------------------------------------------------------- #


class TestLiveEventView:
    def test_audio_chunks(self):
        view = _LiveEventView(_event(parts=[_part(audio=b"\x01\x02")]))
        assert view.audio_chunks == [b"\x01\x02"]

    def test_empty_audio_part_ignored(self):
        # inline_data present but empty → not counted as audio.
        view = _LiveEventView(_event(parts=[_part(audio=b"")]))
        assert view.audio_chunks == []

    def test_function_call_exposes_id_and_args(self):
        call = _fcall("get_weather", id="fc-1", args={"city": "SF"})
        view = _LiveEventView(_event(parts=[_part(fcall=call)]))
        (got,) = view.function_calls
        assert (got.name, got.id, got.args) == ("get_weather", "fc-1", {"city": "SF"})

    def test_function_response_exposes_id_and_response(self):
        resp = _fresp("get_weather", id="fc-1", response={"temp": 68})
        view = _LiveEventView(_event(parts=[_part(fresp=resp)]))
        (got,) = view.function_responses
        assert (got.name, got.id, got.response) == ("get_weather", "fc-1", {"temp": 68})

    def test_unnamed_function_call_ignored(self):
        # A part whose function_call has no name isn't a real call.
        view = _LiveEventView(_event(parts=[_part(fcall=_fcall(None))]))
        assert view.function_calls == []

    def test_partial_vs_final_user_transcript(self):
        partial = _LiveEventView(_event(input_transcription=_txn("hi")))
        assert partial.user_transcript == "hi"
        assert partial.final_user_transcript is None

        final = _LiveEventView(_event(input_transcription=_txn("hi", finished=True)))
        assert final.final_user_transcript == "hi"

    def test_partial_vs_final_agent_transcript(self):
        partial = _LiveEventView(_event(output_transcription=_txn("sun")))
        assert partial.agent_transcript == "sun"
        assert partial.final_agent_transcript is None

        final = _LiveEventView(
            _event(output_transcription=_txn("sunny", finished=True))
        )
        assert final.final_agent_transcript == "sunny"

    def test_interrupted_and_turn_complete_flags(self):
        view = _LiveEventView(_event(interrupted=True, turn_complete=True))
        assert view.interrupted is True
        assert view.turn_complete is True

    def test_empty_event(self):
        view = _LiveEventView(_event())
        assert view.audio_chunks == []
        assert view.function_calls == []
        assert view.final_user_transcript is None
        assert view.final_agent_transcript is None


# --------------------------------------------------------------------------- #
# _usage_metadata — genai usage → LangSmith token usage.
# --------------------------------------------------------------------------- #


class TestUsageMetadata:
    def test_none_when_absent(self):
        assert _usage_metadata(_event()) is None

    def test_maps_token_counts(self):
        um = SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, total_token_count=15
        )
        assert _usage_metadata(_event(usage_metadata=um)) == {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }

    def test_omits_missing_and_non_int_fields(self):
        um = SimpleNamespace(
            prompt_token_count=10, candidates_token_count=None, total_token_count="x"
        )
        assert _usage_metadata(_event(usage_metadata=um)) == {"input_tokens": 10}


# --------------------------------------------------------------------------- #
# _session_key — per-conversation key precedence.
# --------------------------------------------------------------------------- #


class TestSessionKey:
    def test_prefers_session_id(self):
        ctx = _ctx(session_id="sess-1", invocation_id="inv-1")
        assert LangSmithGoogleADKLivePlugin._session_key(ctx) == "sess-1"

    def test_falls_back_to_invocation_id(self):
        ctx = _ctx(session_id=None, invocation_id="inv-1")
        assert LangSmithGoogleADKLivePlugin._session_key(ctx) == "inv-1"

    def test_falls_back_to_object_identity(self):
        ctx = _ctx(session_id=None, invocation_id=None)
        assert LangSmithGoogleADKLivePlugin._session_key(ctx) == str(id(ctx))


# --------------------------------------------------------------------------- #
# Lifecycle + concurrent-conversation isolation.
# --------------------------------------------------------------------------- #


class TestLifecycle:
    def test_before_run_creates_keyed_tracer(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        assert list(plugin._sessions) == ["A"]
        assert plugin._sessions["A"].session is created[0]

    def test_max_audio_seconds_is_plumbed_to_start_session(self, monkeypatch):
        # The audio cap must reach start_session (it bounds per-channel memory on
        # a shared, possibly long-running plugin).
        calls = []

        def fake_start_session(**kwargs):
            calls.append(kwargs)
            return MagicMock()

        monkeypatch.setattr(adk_plugin, "start_session", fake_start_session)
        plugin = _new_plugin(max_audio_seconds=30.0)
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        assert calls[0]["max_audio_seconds"] == 30.0

    def test_client_and_replicas_are_plumbed_to_start_session(self, monkeypatch):
        # An explicit client / replicas must reach start_session so tracing
        # writes can be routed and mirrored per the caller's configuration.
        calls = []

        def fake_start_session(**kwargs):
            calls.append(kwargs)
            return MagicMock()

        monkeypatch.setattr(adk_plugin, "start_session", fake_start_session)
        client = MagicMock()
        replicas = [{"project_name": "replica"}]
        plugin = _new_plugin(client=client, replicas=replicas)
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        assert calls[0]["client"] is client
        assert calls[0]["replicas"] == replicas

    def test_integration_attribution_is_plumbed_to_start_session(self, monkeypatch):
        # The trace must be attributable to this integration + the ADK version.
        calls = []

        def fake_start_session(**kwargs):
            calls.append(kwargs)
            return MagicMock()

        monkeypatch.setattr(adk_plugin, "start_session", fake_start_session)
        plugin = _new_plugin()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        assert calls[0]["integration"] == "google-adk-live"
        # Version comes from the installed google-adk package (str or None).
        assert "integration_version" in calls[0]

    def test_two_conversations_are_isolated(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        ctx_a = _ctx(session_id="A")
        ctx_b = _ctx(session_id="B")

        _run(plugin.before_run_callback(invocation_context=ctx_a))
        _run(plugin.before_run_callback(invocation_context=ctx_b))
        sess_a, sess_b = created[0], created[1]

        # An event on A routes only to A's session.
        _run(
            plugin.on_event_callback(
                invocation_context=ctx_a,
                event=_event(input_transcription=_txn("hello A", finished=True)),
            )
        )
        sess_a.add_message.assert_called_once_with("user", "hello A")
        sess_a.set_title.assert_called_once_with("hello A")
        sess_b.add_message.assert_not_called()

        # Finalizing A leaves B untouched and still active.
        _run(plugin.after_run_callback(invocation_context=ctx_a))
        sess_a.finalize.assert_called_once()
        sess_b.finalize.assert_not_called()
        assert list(plugin._sessions) == ["B"]

        _run(plugin.after_run_callback(invocation_context=ctx_b))
        sess_b.finalize.assert_called_once()
        assert plugin._sessions == {}

    def test_after_run_is_idempotent(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        ctx = _ctx(session_id="A")
        _run(plugin.before_run_callback(invocation_context=ctx))

        _run(plugin.after_run_callback(invocation_context=ctx))
        _run(plugin.after_run_callback(invocation_context=ctx))
        created[0].finalize.assert_called_once()

    def test_finalize_by_session_id_for_appdriven_teardown(self, make_plugin):
        # App-driven teardown (e.g. Ctrl-C) finalizes a specific conversation by
        # ADK session id — keyed, not context-less — and is idempotent with the
        # ADK callback.
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))

        plugin.finalize(session_id="A")
        created[0].finalize.assert_called_once()
        assert plugin._sessions == {}

        # Unknown id and repeat calls are no-ops.
        plugin.finalize(session_id="A")  # already finalized
        plugin.finalize(session_id="ghost")
        created[0].finalize.assert_called_once()


# --------------------------------------------------------------------------- #
# observe — flat event spans, single tool span, markers.
# --------------------------------------------------------------------------- #


class TestObserve:
    def _start(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        ctx = _ctx(session_id="A")
        _run(plugin.before_run_callback(invocation_context=ctx))
        return plugin, ctx, created[0]

    def _emit(self, plugin, ctx, event):
        _run(plugin.on_event_callback(invocation_context=ctx, event=event))

    def test_audio_only_event_is_not_spanned(self, make_plugin):
        plugin, ctx, session = self._start(make_plugin)
        self._emit(plugin, ctx, _event(parts=[_part(audio=b"\x01\x02")]))
        session.event_span.assert_not_called()
        session.open_span.assert_not_called()
        session.add_message.assert_not_called()

    def test_final_user_transcript_rolls_up_and_spans(self, make_plugin):
        plugin, ctx, session = self._start(make_plugin)
        self._emit(
            plugin, ctx, _event(input_transcription=_txn("weather?", finished=True))
        )
        # No turn grouping — the utterance is a flat, point-in-time span.
        session.start_turn.assert_not_called()
        session.add_message.assert_called_once_with("user", "weather?")
        session.set_title.assert_called_once_with("weather?")
        session.event_span.assert_called_once()
        assert session.event_span.call_args.kwargs["name"] == "input_transcription"

    def test_partial_transcript_is_ignored(self, make_plugin):
        # Streaming partials must not flood the trace: no span or rollup until the
        # transcript is finalized.
        plugin, ctx, session = self._start(make_plugin)
        self._emit(plugin, ctx, _event(input_transcription=_txn("weath")))
        session.add_message.assert_not_called()
        session.event_span.assert_not_called()

    def test_final_agent_transcript_spans_output_transcription(self, make_plugin):
        # The agent response is a flat, point-in-time ``output_transcription``
        # span (anchored at event arrival), carrying token usage — not a
        # synthetic ``model`` / turn-grouped span.
        plugin, ctx, session = self._start(make_plugin)
        um = SimpleNamespace(
            prompt_token_count=3, candidates_token_count=2, total_token_count=5
        )
        self._emit(
            plugin,
            ctx,
            _event(
                output_transcription=_txn("sunny", finished=True), usage_metadata=um
            ),
        )
        session.add_message.assert_called_once_with("assistant", "sunny")
        session.set_title.assert_not_called()  # title only set from user speech
        session.record_llm.assert_not_called()
        session.start_turn.assert_not_called()
        session.event_span.assert_called_once()
        kwargs = session.event_span.call_args.kwargs
        assert kwargs["name"] == "output_transcription"
        assert kwargs["usage_metadata"] == {
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }

    def test_tool_call_is_one_span_start_to_end(self, make_plugin):
        # function_call opens a held-open ``tool`` span; the matching
        # function_response closes it (real tool latency = the gap between).
        plugin, ctx, session = self._start(make_plugin)
        run = MagicMock(name="tool-run")
        session.open_span.return_value = run

        self._emit(
            plugin,
            ctx,
            _event(
                parts=[_part(fcall=_fcall("get_weather", id="fc-1", args={"c": "SF"}))]
            ),
        )
        session.open_span.assert_called_once()
        open_kwargs = session.open_span.call_args.kwargs
        assert open_kwargs["name"] == "get_weather"
        assert open_kwargs["run_type"] == "tool"
        assert open_kwargs["inputs"] == {"args": {"c": "SF"}}
        assert open_kwargs["metadata"]["function_call_id"] == "fc-1"
        session.close_span.assert_not_called()  # still open

        self._emit(
            plugin,
            ctx,
            _event(
                parts=[
                    _part(fresp=_fresp("get_weather", id="fc-1", response={"t": 68}))
                ]
            ),
        )
        session.close_span.assert_called_once()
        assert session.close_span.call_args.args[0] is run
        assert session.close_span.call_args.kwargs["outputs"] == {"response": {"t": 68}}

    def test_parallel_tool_calls_match_by_id(self, make_plugin):
        plugin, ctx, session = self._start(make_plugin)
        run1, run2 = MagicMock(name="run1"), MagicMock(name="run2")
        session.open_span.side_effect = [run1, run2]

        # Two calls open in one event; responses arrive in the opposite order.
        self._emit(
            plugin,
            ctx,
            _event(
                parts=[
                    _part(fcall=_fcall("a", id="fc-1")),
                    _part(fcall=_fcall("b", id="fc-2")),
                ]
            ),
        )
        self._emit(
            plugin,
            ctx,
            _event(
                parts=[
                    _part(fresp=_fresp("b", id="fc-2")),
                    _part(fresp=_fresp("a", id="fc-1")),
                ]
            ),
        )
        closed = [c.args[0] for c in session.close_span.call_args_list]
        assert closed == [run2, run1]  # fc-2 then fc-1, matched by id

    def test_orphan_response_falls_back_to_point_in_time_span(self, make_plugin):
        # A response with no open call (tracing began mid-call) still records the
        # tool as a point-in-time span rather than being dropped.
        plugin, ctx, session = self._start(make_plugin)
        self._emit(
            plugin,
            ctx,
            _event(parts=[_part(fresp=_fresp("get_weather", id="ghost", response={}))]),
        )
        session.open_span.assert_not_called()
        session.close_span.assert_not_called()
        session.event_span.assert_called_once()
        assert session.event_span.call_args.kwargs["run_type"] == "tool"

    def test_orphan_open_tool_closed_with_error_on_finalize(self, make_plugin):
        # A call whose tool raised (no function_response event) must not dangle:
        # teardown closes it with an error.
        plugin, ctx, session = self._start(make_plugin)
        run = MagicMock(name="tool-run")
        session.open_span.return_value = run
        self._emit(plugin, ctx, _event(parts=[_part(fcall=_fcall("boom", id="fc-1"))]))

        _run(plugin.after_run_callback(invocation_context=ctx))
        assert run.error == "tool did not complete before the session ended"
        session.close_span.assert_called_once_with(run)
        session.finalize.assert_called_once()

    def test_interrupted_keeps_marker(self, make_plugin):
        plugin, ctx, session = self._start(make_plugin)
        self._emit(plugin, ctx, _event(interrupted=True))
        session.event_span.assert_called_once()
        assert session.event_span.call_args.kwargs["name"] == "interrupted"

    def test_turn_complete_keeps_marker(self, make_plugin):
        plugin, ctx, session = self._start(make_plugin)
        self._emit(plugin, ctx, _event(turn_complete=True))
        session.event_span.assert_called_once()
        assert session.event_span.call_args.kwargs["name"] == "turn_complete"

    def test_event_for_unknown_session_is_noop(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()  # no before_run for this ctx
        self._emit(plugin, _ctx(session_id="ghost"), _event(turn_complete=True))
        assert created == []  # start_session never called


# --------------------------------------------------------------------------- #
# Audio routing.
# --------------------------------------------------------------------------- #


class TestAudioRouting:
    def test_explicit_session_id_routes(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))

        plugin.record_user_audio(b"pcm", session_id="A")
        created[0].record_user.assert_called_once()
        assert created[0].record_user.call_args[0][1] == b"pcm"

    def test_single_active_session_default_routes(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))

        plugin.record_agent_audio(b"pcm")  # no session_id, one active → routed
        created[0].record_agent.assert_called_once()
        assert created[0].record_agent.call_args[0][1] == b"pcm"

    def test_ambiguous_without_session_id_is_dropped(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="B")))

        plugin.record_user_audio(b"pcm")  # two active, ambiguous → dropped
        created[0].record_user.assert_not_called()
        created[1].record_user.assert_not_called()

    def test_no_active_session_is_dropped(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        plugin.record_user_audio(b"pcm")  # no sessions → silently dropped
        assert created == []

    def test_unknown_session_id_is_dropped(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))

        plugin.record_user_audio(b"pcm", session_id="Z")
        created[0].record_user.assert_not_called()


# --------------------------------------------------------------------------- #
# Exception isolation — tracing failures never propagate into the live loop.
# --------------------------------------------------------------------------- #


class TestExceptionIsolation:
    def test_before_run_swallows_errors(self, monkeypatch):
        monkeypatch.setattr(
            adk_plugin, "start_session", MagicMock(side_effect=RuntimeError("boom"))
        )
        plugin = _new_plugin()
        # Must not raise, and no session should be registered.
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        assert plugin._sessions == {}

    def test_on_event_swallows_errors(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        ctx = _ctx(session_id="A")
        _run(plugin.before_run_callback(invocation_context=ctx))
        created[0].event_span.side_effect = RuntimeError("boom")
        # Must not raise despite the span failing.
        _run(
            plugin.on_event_callback(
                invocation_context=ctx,
                event=_event(turn_complete=True),
            )
        )

    def test_after_run_swallows_errors_and_still_pops(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        ctx = _ctx(session_id="A")
        _run(plugin.before_run_callback(invocation_context=ctx))
        created[0].finalize.side_effect = RuntimeError("boom")

        _run(plugin.after_run_callback(invocation_context=ctx))
        # Session is popped before finalize, so a failure still clears state.
        assert plugin._sessions == {}

    def test_record_audio_swallows_errors(self, make_plugin):
        factory, created = make_plugin
        plugin = factory()
        _run(plugin.before_run_callback(invocation_context=_ctx(session_id="A")))
        created[0].record_user.side_effect = RuntimeError("boom")
        # Must not raise into the app's audio path.
        plugin.record_user_audio(b"pcm", session_id="A")


# --------------------------------------------------------------------------- #
# Public surface.
# --------------------------------------------------------------------------- #


class TestBetaWarning:
    def test_construction_emits_beta_warning(self):
        _warn_once.cache_clear()  # @warn_beta dedupes per message; reset it
        with pytest.warns(LangSmithBetaWarning):
            LangSmithGoogleADKLivePlugin()
