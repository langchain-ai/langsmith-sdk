"""Hybrid-mode batch handling, with the network faked out.

Hybrid mode sends every batch twice: once as a LangSmith HTTP payload, once as
OTEL spans. This measures what the handler itself costs per batch -- combining
the queued operations and driving both legs -- with the transport replaced by a
counter.
"""

from langsmith._internal._background_thread import (
    TracingQueueItem,
    _hybrid_tracing_thread_handle_batch,
)
from langsmith._internal._operations import serialize_run_dict


class FakeClient:
    """Just enough Client for the hybrid handler: a send counter and an OTEL sink."""

    def __init__(self):
        self.sends = 0
        self.otel_exporter = self

    def _multipart_ingest_ops(self, ops, **kwargs):
        self.sends += 1

    def export_batch(self, run_ops, otel_context_map):
        pass  # the real exporter only builds spans in memory

    def _invoke_tracing_error_callback(self, error):
        # Both legs log and swallow their own errors, so a double that got a
        # signature wrong would otherwise look like a pass that measured nothing.
        raise AssertionError(f"a leg failed, so this measured nothing: {error!r}")


def make_batches(count, ops_per_batch):
    """Prepare the input up front so serialization is not in the timing."""
    batches = []
    for batch_index in range(count):
        items = []
        for i in range(ops_per_batch):
            run_id = f"00000000-0000-4000-8000-{batch_index:06d}{i:06d}"
            op = serialize_run_dict(
                "post",
                {
                    "id": run_id,
                    "trace_id": run_id,
                    "dotted_order": f"20231201T120000000000Z{run_id}",
                    "session_name": "Session Name",
                    "name": f"run_{i}",
                    "run_type": "llm",
                    "inputs": {"messages": [{"role": "user", "content": "hello"}]},
                    "outputs": {"text": "hi"},
                },
            )
            items.append(TracingQueueItem(f"priority_{i}", op))
        batches.append(items)
    return batches


def handle_hybrid_batches(batches):
    """Run every prepared batch through the hybrid handler on this thread."""
    client = FakeClient()
    for batch in batches:
        # No queue: nothing touches it while mark_task_done is False.
        _hybrid_tracing_thread_handle_batch(client, None, batch, True, False)
    assert client.sends == len(batches)
