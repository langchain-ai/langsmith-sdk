"""WAV reconstruction for the voice integrations.

* ``pcm_to_wav`` — wrap already-merged PCM16 bytes in a WAV container. Used by the
  Pipecat processor (whose ``AudioBufferProcessor`` emits merged stereo audio).
* ``build_stereo_session_wav`` — reconstruct one stereo conversation WAV from the
  timestamped PCM16 chunks each side recorded (L=user, R=agent), laid out at
  natural play time so bursts don't overlap. Used by the Track-B ``EventSession``.
"""

from __future__ import annotations

import array
import io
import math
import wave

DEFAULT_MAX_AUDIO_SECONDS = 10 * 60


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


def _layout_chunks_to_play_time(
    chunks: list[tuple[float, bytes]], sample_rate: int
) -> list[tuple[float, bytes]]:
    """Rewrite receipt timestamps into natural-play timestamps.

    Receipt times reflect when bytes arrived from the source, not when they
    play. The agent channel especially arrives in bursts faster than realtime —
    multiple chunks can land within a few ms of each other, and placing them at
    receipt time makes them overlap and overwrite each other (you hear scrambled
    tail-ends). The correct natural play time for a chunk is the LATER of where
    the previous chunk ended and when this chunk arrived, which preserves real
    gaps between bursts and keeps consecutive bursts contiguous.
    """
    out: list[tuple[float, bytes]] = []
    cur_time = 0.0
    for i, (t_recv, data) in enumerate(chunks):
        cur_time = t_recv if i == 0 else max(cur_time, t_recv)
        out.append((cur_time, data))
        cur_time += (len(data) // 2) / sample_rate
    return out


def _chunk_end(t: float, data: bytes, sample_rate: int) -> float:
    return t + (len(data) // 2) / sample_rate


def session_wav_exceeds_duration_cap(
    user_chunks: list[tuple[float, bytes]],
    agent_chunks: list[tuple[float, bytes]],
    sample_rate: int,
    max_duration_seconds: float | None,
) -> bool:
    """Return whether natural-play WAV layout exceeds the duration cap."""
    if max_duration_seconds is None:
        return False
    user = _layout_chunks_to_play_time(user_chunks, sample_rate)
    agent = _layout_chunks_to_play_time(agent_chunks, sample_rate)
    user_end = max((_chunk_end(t, d, sample_rate) for t, d in user), default=0.0)
    agent_end = max((_chunk_end(t, d, sample_rate) for t, d in agent), default=0.0)
    return max(user_end, agent_end) > max_duration_seconds


def build_stereo_session_wav(
    user_chunks: list[tuple[float, bytes]],
    agent_chunks: list[tuple[float, bytes]],
    sample_rate: int,
    *,
    max_duration_seconds: float | None = DEFAULT_MAX_AUDIO_SECONDS,
) -> bytes:
    """Reconstruct a duration-capped stereo WAV from timestamped PCM16 chunks.

    Left channel = user, right channel = agent. Both channels are laid out at
    natural play time (see ``_layout_chunks_to_play_time``). Gaps between bursts
    are silence; overlap between user and agent (during a barge-in) is preserved
    because they live on different channels.
    """
    if not user_chunks and not agent_chunks:
        return b""

    user = _layout_chunks_to_play_time(user_chunks, sample_rate)
    agent = _layout_chunks_to_play_time(agent_chunks, sample_rate)

    user_end = max((_chunk_end(t, d, sample_rate) for t, d in user), default=0.0)
    agent_end = max((_chunk_end(t, d, sample_rate) for t, d in agent), default=0.0)
    total_samples = int(math.ceil(max(user_end, agent_end) * sample_rate))
    if max_duration_seconds is not None:
        max_samples = int(math.ceil(max_duration_seconds * sample_rate))
        total_samples = min(total_samples, max_samples)
    if total_samples <= 0:
        return b""

    def mono_channel(chunks: list[tuple[float, bytes]]) -> array.array:
        # One zero-filled PCM16 channel; each chunk is copied in at its offset.
        # The layout guarantees chunks within a channel never overlap, so a
        # plain slice assignment is correct.
        chan = array.array("h", bytes(2 * total_samples))
        for t, data in chunks:
            offset = int(t * sample_rate)
            samples = array.array("h", data[: 2 * (len(data) // 2)])
            n = min(len(samples), total_samples - offset)
            if n > 0:
                chan[offset : offset + n] = samples[:n]
        return chan

    left = mono_channel(user)  # user channel
    right = mono_channel(agent)  # agent channel

    # Interleave L/R via extended-slice assignment (a C-level strided copy).
    # Overlap between the two parties is preserved: they live on separate channels.
    stereo = array.array("h", bytes(4 * total_samples))
    stereo[0::2] = left
    stereo[1::2] = right

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())
    return wav_io.getvalue()
