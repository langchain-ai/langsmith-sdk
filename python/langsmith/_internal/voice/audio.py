"""WAV reconstruction for the Track-A voice span processors.

``pcm_to_wav`` wraps already-merged PCM16 bytes (e.g. the output of Pipecat's
``AudioBufferProcessor``) in a WAV container so a processor can attach the
recorded conversation to a span.
"""

from __future__ import annotations

import io
import wave


def pcm_to_wav(pcm: bytes, sample_rate: int, num_channels: int = 1) -> bytes:
    """Wrap raw PCM16 bytes in a WAV container.

    For already-merged PCM (e.g. the output of Pipecat's ``AudioBufferProcessor``,
    where ``num_channels=2`` is user-left / bot-right). Returns ``b""`` for empty
    input.
    """
    if not pcm:
        return b""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
