"""Unit tests for the shared Track-B ``_voice`` helpers.

The stereo-WAV builder (``_voice/audio.py``) and the event-payload sanitizers
(``_voice/helpers.py``) are used by ``EventSession`` and ship with it. Pure
helpers — no framework import needed.
"""

import io
import wave
from unittest.mock import MagicMock

import pytest

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice import audio as audio_utils
from langsmith._internal.voice import helpers
from langsmith.anonymizer import SECRET_PLACEHOLDER


class TestVoiceAudio:
    """Stereo session WAV reconstruction in ``_voice/audio.py``."""

    def test_layout_chunks_to_play_time_keeps_bursts_contiguous(self):
        # Two single-sample chunks (2 bytes each) received at t=0, sr=2 → the
        # second is laid out at 0.5s so it does not overwrite the first.
        chunks = [(0.0, b"\x00\x00"), (0.0, b"\x00\x00")]
        out = audio_utils._layout_chunks_to_play_time(chunks, sample_rate=2)
        assert [round(t, 3) for t, _ in out] == [0.0, 0.5]

    def test_build_stereo_session_wav_empty(self):
        assert audio_utils.build_stereo_session_wav([], [], 16000) == b""

    def test_build_stereo_session_wav_produces_stereo(self):
        user = [(0.0, b"\x01\x00" * 4)]
        agent = [(0.0, b"\x02\x00" * 4)]
        wav = audio_utils.build_stereo_session_wav(user, agent, 16000)
        assert wav[:4] == b"RIFF"
        with wave.open(io.BytesIO(wav), "rb") as wf:
            assert wf.getnchannels() == 2


class TestVoiceHelpers:
    """Event payload sanitization in ``_voice/helpers.py``."""

    def test_scrub_replaces_bytes_and_truncates(self):
        assert helpers.scrub(b"abc") == "<3 bytes>"
        long = "x" * (helpers.MAX_STR + 50)
        scrubbed = helpers.scrub(long)
        assert scrubbed.startswith("x" * helpers.MAX_STR)
        assert "<+50 chars>" in scrubbed

    def test_scrub_recurses(self):
        assert helpers.scrub({"a": b"xy", "b": [b"z"]}) == {
            "a": "<2 bytes>",
            "b": ["<1 bytes>"],
        }

    def test_scrub_masks_realtime_session_tool_credentials(self):
        """Hosted MCP tools in a session carry a bearer token and auth headers."""
        token = "fake-token-for-tests-only"
        event = {
            "type": "session.updated",
            "session": {
                "model": "gpt-realtime",
                "tools": [
                    {
                        "type": "mcp",
                        "server_label": "example",
                        "server_url": "https://mcp.example.com/sse",
                        "authorization": token,
                        "headers": {"Authorization": f"Bearer {token}"},
                    }
                ],
            },
        }

        scrubbed = helpers.scrub(event)

        assert token not in str(scrubbed)
        tool = scrubbed["session"]["tools"][0]
        assert tool["authorization"] == SECRET_PLACEHOLDER
        assert tool["headers"] == {"Authorization": SECRET_PLACEHOLDER}
        assert tool["server_label"] == "example"
        assert scrubbed["session"]["model"] == "gpt-realtime"

    @pytest.mark.parametrize(
        "key",
        ["authorization", "api_key", "headers", "env", "access_token", "password"],
    )
    def test_scrub_masks_credential_keys(self, key):
        assert helpers.scrub({key: "s3cret"}) == {key: SECRET_PLACEHOLDER}

    def test_scrub_keeps_mapping_key_names_when_masking(self):
        scrubbed = helpers.scrub({"env": {"ANTHROPIC_API_KEY": "s3cret"}})

        assert scrubbed == {"env": {"ANTHROPIC_API_KEY": SECRET_PLACEHOLDER}}

    @pytest.mark.parametrize(
        "key", ["max_tokens", "token_count", "input_tokens", "top_logprobs"]
    )
    def test_scrub_leaves_lookalike_keys_alone(self, key):
        """Matching is on exact keys, so `token` substrings survive."""
        assert helpers.scrub({key: 128}) == {key: 128}

    def test_scrub_masks_inside_lists(self):
        event = {"items": [{"headers": {"Authorization": "s3cret"}}]}

        assert helpers.scrub(event) == {
            "items": [{"headers": {"Authorization": SECRET_PLACEHOLDER}}]
        }

    def test_scrub_does_not_mutate_the_caller(self):
        event = {"session": {"authorization": "s3cret"}}

        helpers.scrub(event)

        assert event["session"]["authorization"] == "s3cret"

    def test_dump_event_variants(self):
        model = MagicMock()
        model.model_dump.return_value = {"k": "v"}
        assert helpers.dump_event(model) == {"k": "v"}
        assert helpers.dump_event({"already": "dict"}) == {"already": "dict"}
        assert "repr" in helpers.dump_event(object())

    def test_get_package_version_installed(self):
        # langsmith itself is always importable in the test env.
        assert get_package_version("langsmith") is not None

    def test_get_package_version_missing_returns_none(self):
        assert get_package_version("no-such-package-xyz-123") is None
