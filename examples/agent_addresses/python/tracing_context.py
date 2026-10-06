"""Address everything traced inside a block with `tracing_context`.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python tracing_context.py`.
"""

import langsmith as ls

client = ls.Client()


@ls.traceable(client=client)
def handle_order(order_id: str) -> dict:
    return {"order_id": order_id, "status": "charged"}


with ls.tracing_context(address=ls.Agent("checkout", "staging")):
    handle_order("A-1")
client.flush()
