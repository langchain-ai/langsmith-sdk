"""Unit tests for the shared Track-B ``EventSession`` (``_voice/session.py``).

``EventSession`` builds the LangSmith ``RunTree`` for an observed event stream:
the conversation root, per-event/turn child spans, the transcript rollup, the
audio buffers, and ``finalize``. These tests drive it against a mocked client so
no network is touched, asserting the in-memory trace state it produces.
"""

from __future__ import annotations

from unittest import mock

import pytest

from langsmith import Client
from langsmith._internal.voice import session as session_mod
from langsmith._internal.voice.session import EventSession, start_session

LS_TEST_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}


@pytest.fixture
def mock_client() -> Client:
    return Client(session=mock.MagicMock(), info=LS_TEST_CLIENT_INFO, api_key="test")


@pytest.fixture(autouse=True)
def _patch_cached_client(mock_client, monkeypatch):
    # Every RunTree built by start_session resolves its client lazily via
    # run_trees.get_cached_client(); point it at the mock so .post()/.patch()
    # enqueue to a fake session instead of the network.
    monkeypatch.setattr(
        "langsmith.run_trees.get_cached_client", lambda **_: mock_client
    )


def _session(**kwargs) -> EventSession:
    kwargs.setdefault("integration", "test-integration")
    return start_session(thread_id="t1", sample_rate=24_000, **kwargs)


class TestAudioBound:
    """``max_audio_seconds`` → bounded per-channel PCM retention."""

    def test_start_session_converts_seconds_to_bytes(self):
        # 2s at 24kHz PCM16 = 2 * 24000 * 2 bytes per channel.
        s = _session(max_audio_seconds=2.0)
        assert s.max_audio_bytes == 2 * 24_000 * 2

    def test_no_cap_by_default(self):
        s = _session()
        assert s.max_audio_bytes is None
        for _ in range(5):
            s.record_user(0.0, b"\x00\x00" * 1000)
        assert len(s.user_chunks) == 5
        assert s._audio_truncated is False

    def test_user_channel_capped_and_flagged_once(self):
        s = _session()
        s.max_audio_bytes = 100  # tiny cap for the test
        s.record_user(0.0, b"\x00" * 80)  # under cap → kept
        s.record_user(0.1, b"\x00" * 80)  # now at/over cap → kept, pushes over
        s.record_user(0.2, b"\x00" * 80)  # dropped
        s.record_user(0.3, b"\x00" * 80)  # dropped
        assert len(s.user_chunks) == 2
        assert s._user_bytes == 160
        assert s._audio_truncated is True

    def test_cap_is_per_channel(self):
        s = _session()
        s.max_audio_bytes = 100
        s.record_user(0.0, b"\x00" * 200)  # user over cap
        s.record_agent(0.0, b"\x00" * 50)  # agent still under
        s.record_agent(0.1, b"\x00" * 50)
        assert len(s.user_chunks) == 1
        assert len(s.agent_chunks) == 2  # agent unaffected by the user cap

    def test_truncation_surfaced_in_root_metadata(self):
        s = _session()
        s.max_audio_bytes = 10
        s.record_user(0.0, b"\x00" * 20)
        s.record_user(0.1, b"\x00" * 20)  # dropped → truncated
        s.finalize()
        meta = (s.run.extra or {}).get("metadata") or {}
        assert meta.get("audio_truncated") is True


class TestIntegrationMetadata:
    """``integration`` / ``integration_version`` → ``ls_integration*`` on root."""

    def test_stamped_on_root(self):
        s = _session(integration="google-adk-live", integration_version="2.2.0")
        meta = (s.run.extra or {}).get("metadata") or {}
        assert meta["ls_integration"] == "google-adk-live"
        assert meta["ls_integration_version"] == "2.2.0"

    def test_unresolved_version_recorded_as_none(self):
        # An unresolvable framework version records the integration id anyway,
        # with a null version (the RunTree metadata path allows null).
        s = _session(integration="pipecat", integration_version=None)
        meta = (s.run.extra or {}).get("metadata") or {}
        assert meta["ls_integration"] == "pipecat"
        assert meta["ls_integration_version"] is None

    def test_caller_metadata_cannot_shadow_integration(self):
        s = _session(
            integration="livekit",
            integration_version="1.0.0",
            metadata={"ls_integration": "spoofed"},
        )
        meta = (s.run.extra or {}).get("metadata") or {}
        assert meta["ls_integration"] == "livekit"


class TestTranscriptAndTitle:
    def test_add_message_strips_and_drops_empty(self):
        s = _session()
        s.add_message("user", "  hello  ")
        s.add_message("assistant", "   ")  # whitespace only → dropped
        assert s.messages == [{"role": "user", "content": "hello"}]

    def test_set_title_first_nonempty_wins(self):
        s = _session()
        s.set_title("")  # ignored
        s.set_title("first question")
        s.set_title("second")  # ignored, first wins
        # The title names the root run (what LangSmith displays), not metadata.
        assert s.run.name == "first question"

    def test_finalize_rolls_transcript_onto_root(self):
        s = _session()
        s.add_message("user", "hi")
        s.add_message("assistant", "hello")
        s.finalize()
        assert s.run.outputs == {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        }


class TestTurns:
    def test_turn_groups_messages_and_carries_metadata(self):
        s = _session()
        s.start_turn()
        s.add_message("user", "weather?")
        s.add_turn_metadata(was_interrupted=True, latency_to_first_audio_ms=120)
        # Read the open turn span before finalize closes it.
        turn = s._current_turn
        assert turn is not None
        meta = (turn.extra or {}).get("metadata") or {}
        assert meta["turn"] == 1
        assert meta["was_interrupted"] is True
        assert meta["latency_to_first_audio_ms"] == 120
        s.finalize()
        # Its messages were rolled up as the turn's outputs on close.
        assert turn.outputs == {"messages": [{"role": "user", "content": "weather?"}]}

    def test_add_turn_metadata_noop_without_open_turn(self):
        s = _session()
        # No start_turn called → nothing to attach to, must not raise.
        s.add_turn_metadata(was_interrupted=True)


class TestRecordLlm:
    def test_default_inputs_drop_trailing_assistant(self):
        s = _session()
        s.add_message("user", "hi")
        s.add_message("assistant", "the answer")  # the response being recorded
        captured: list = []
        real_create = session_mod.RunTree.create_child

        def spy(self, **kwargs):
            child = real_create(self, **kwargs)
            if kwargs.get("run_type") == "llm":
                captured.append(child)
            return child

        with mock.patch.object(session_mod.RunTree, "create_child", spy):
            s.record_llm(outputs={"role": "assistant", "content": "the answer"})
        # The effective prompt is history minus the trailing assistant response.
        assert len(captured) == 1
        assert captured[0].inputs == {"messages": [{"role": "user", "content": "hi"}]}


class TestFinalizeFailOpen:
    def test_wav_build_failure_does_not_break_finalize(self, monkeypatch):
        s = _session()
        s.add_message("user", "hi")
        monkeypatch.setattr(
            session_mod,
            "build_stereo_session_wav",
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        s.finalize()  # must not raise
        # Root still closed with the transcript despite the WAV failure, and no
        # audio attachment was set.
        assert s.run.outputs == {"messages": [{"role": "user", "content": "hi"}]}
        assert not s.run.attachments
