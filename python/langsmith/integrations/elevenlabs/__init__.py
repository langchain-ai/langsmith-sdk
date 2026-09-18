"""LangSmith tracing for ElevenLabs Agents.

ElevenLabs runs the agent on its own servers and emits a finished OTLP trace
afterwards, as the ``post_call_transcription_otel`` webhook (enabled by setting
the webhook's ``transcript_format`` to ``opentelemetry``). Verify that webhook in
your application, then hand its OTLP envelope here::

    from langsmith.integrations.elevenlabs import export_elevenlabs_trace

    export_elevenlabs_trace(event["data"]["otlp_traces"], audio=mp3_bytes)

The same envelope is returned by ``GET /v1/convai/conversations/{id}
?format=opentelemetry``, so a trace can be exported without a webhook at all.

``audio`` is the conversation recording and is optional — omit it and the trace
exports without one. Raw MP3 bytes are the usual form, as returned by
``conversations.audio.get(...)``; a ``post_call_audio`` webhook payload works
too. Fetching the recording yourself is deliberate: this integration never calls
ElevenLabs, so it needs no API key of its own. Note that LangSmith cannot attach
audio to a trace after the fact, so pass it on the one export or not at all.

The functions preserve ElevenLabs' topology and attributes, attach the MP3 to
the conversation root, group the trace by ``thread_id``, mark it
``ls_modality=audio``, translate transcript and tool spans into LangSmith runs,
map per-turn token counts onto ``usage_metadata`` with ``ls_provider`` and
``ls_model_name``, and surface every other ``elevenlabs.*`` attribute as run
metadata.

Signature verification belongs to your application: the ``elevenlabs`` package
ships ``client.webhooks.construct_event(...)`` for it, which needs the webhook's
signing secret rather than an API key.
"""

from langsmith.integrations.elevenlabs._otel import (
    DEFAULT_AUDIO_SIZE_LIMIT,
    aexport_elevenlabs_trace,
    export_elevenlabs_trace,
    transform_elevenlabs_trace,
)

__all__ = [
    "DEFAULT_AUDIO_SIZE_LIMIT",
    "aexport_elevenlabs_trace",
    "export_elevenlabs_trace",
    "transform_elevenlabs_trace",
]
