"""Address a block of code with the `trace` context manager.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python trace_context_manager.py`.
"""

import langsmith as ls

client = ls.Client()

with ls.trace(
    "handle_order",
    run_type="chain",
    inputs={"order_id": "A-1"},
    client=client,
    address=ls.Agent("checkout", "production"),
) as run:
    run.end(outputs={"status": "charged"})
client.flush()
