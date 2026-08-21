"""LangSmith tracing for ElevenLabs Agents post-call webhooks.

ElevenLabs sends the complete OTLP trace and combined conversation audio in
separate webhooks.  Verify both webhooks in your application, correlate them by
``conversation_id``, then export one audio-aware LangSmith trace::

    from langsmith.integrations.elevenlabs import export_elevenlabs_trace

    export_elevenlabs_trace(
        otlp_traces=otel_event["data"]["otlp_traces"],
        post_call_audio=audio_event,
        conversation_id=otel_event["data"]["conversation_id"],
        project_name="voice-agents",
    )

The functions preserve ElevenLabs' single-trace topology, attach the MP3 to the
conversation root, mark the trace with ``ls_modality=audio``, and translate
documented transcript/tool attributes for LangSmith's trace and message views.

``post_call_audio`` delivery is not retried by ElevenLabs, so applications
should persist and correlate both events before calling this integration. Audio
is optional: a trace can still be exported if the audio webhook never arrives.
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
