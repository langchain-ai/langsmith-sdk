"""Address a single call with `langsmith_extra`.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python langsmith_extra.py`.
"""

import langsmith as ls

client = ls.Client()


@ls.traceable(client=client)
def handle_order(order_id: str) -> dict:
    return {"order_id": order_id, "status": "charged"}


handle_order("A-1", langsmith_extra={"address": ls.Agent("checkout", "production")})
client.flush()
