import logging
import uuid
from typing import Dict, Optional

from langsmith import run_trees as rt

try:
    from agents import tracing  # type: ignore[import]

    import langsmith.wrappers._agent_utils as agent_utils

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False

    class LangsmithTracingProcessor:
        """Stub class when agents package is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "The `agents` package is not installed. "
                "Please install it with `pip install langsmith[openai-agents]`."
            )


from langsmith import client as ls_client

logger = logging.getLogger(__name__)

if HAVE_AGENTS:

    class LangsmithTracingProcessor(tracing.TracingProcessor):  # type: ignore[no-redef]
        """LangsmithTracingProcessor is a TracingProcessor for the OpenAI Agents SDK.

        It logs traces and spans to Langsmith.

        Args:
            client: An instance of langsmith.client.Client. If not provided,
                a default client is created.
        """

        def __init__(self, client: Optional[ls_client.Client] = None):
            self.client = client or rt.get_cached_client()
            self._runs: Dict[str, str] = {}

        def on_trace_start(self, trace: tracing.Trace) -> None:
            run_name = trace.name if trace.name else "Agent trace"
            trace_run_id = str(uuid.uuid4())
            self._runs[trace.trace_id] = trace_run_id

            try:
                run_data: dict = dict(
                    name=run_name,
                    inputs={},
                    run_type="chain",
                    id=trace_run_id,
                    revision_id=None,
                )
                self.client.create_run(**run_data)
            except Exception as e:
                logger.exception(f"Error creating trace run: {e}")

        def on_trace_end(self, trace: tracing.Trace) -> None:
            run_id = self._runs.pop(trace.trace_id, None)
            if run_id:
                try:
                    self.client.update_run(
                        run_id=run_id,
                    )
                except Exception as e:
                    logger.exception(f"Error updating trace run: {e}")

        def on_span_start(self, span: tracing.Span) -> None:
            parent_run_id = self._runs.get(span.parent_id or span.trace_id)
            span_run_id = str(uuid.uuid4())
            self._runs[span.span_id] = span_run_id

            run_name = agent_utils.get_run_name(span)
            run_type = agent_utils.get_run_type(span)

            try:
                run_data: dict = dict(
                    name=run_name,
                    run_type=run_type,
                    id=span_run_id,
                    parent_run_id=parent_run_id,
                    inputs={},
                )
                self.client.create_run(**run_data)
            except Exception as e:
                logger.exception(f"Error creating span run: {e}")

        def on_span_end(self, span: tracing.Span) -> None:
            run_id = self._runs.pop(span.span_id, None)
            if run_id:
                extracted = agent_utils.extract_span_data(span)
                run_data: dict = dict(
                    run_id=run_id,
                    error=str(span.error) if span.error else None,
                    inputs=extracted.get("inputs", {}),
                    outputs=extracted.get("outputs", {}),
                    extra={"metadata": extracted.get("metadata", {})},
                )
                self.client.update_run(**run_data)

        def shutdown(self) -> None:
            if self.client is not None:
                self.client.flush()
            else:
                logger.warning("No client to flush")

        def force_flush(self) -> None:
            if self.client is not None:
                self.client.flush()
            else:
                logger.warning("No client to flush")
