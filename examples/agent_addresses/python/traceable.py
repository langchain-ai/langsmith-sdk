"""Address a traced function with the `@traceable` decorator.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python traceable.py`.
"""

import langsmith as ls

client = ls.Client()


@ls.traceable(client=client, address=ls.Agent("checkout", "production"))
def handle_order(order_id: str) -> dict:
    return {"order_id": order_id, "status": "charged"}


handle_order("A-1")
client.flush()
