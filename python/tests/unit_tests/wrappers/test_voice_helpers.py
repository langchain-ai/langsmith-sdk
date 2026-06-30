"""Unit tests for the shared Track-B ``_voice`` helpers.

The stereo-WAV builder (``_voice/audio.py``) and the event-payload sanitizers
(``_voice/helpers.py``) are used by ``EventSession`` and ship with it. Pure
helpers — no framework import needed.
"""

import io
import wave
from unittest.mock import MagicMock

from langsmith._internal.voice import audio as audio_utils
from langsmith._internal.voice import helpers


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

    def test_dump_event_variants(self):
        model = MagicMock()
        model.model_dump.return_value = {"k": "v"}
        assert helpers.dump_event(model) == {"k": "v"}
        assert helpers.dump_event({"already": "dict"}) == {"already": "dict"}
        assert "repr" in helpers.dump_event(object())
