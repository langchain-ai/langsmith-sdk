"""Address every traced call in the process with `ls.configure`.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python configure.py`.
"""

import langsmith as ls

client = ls.Client()
ls.configure(client=client, address=ls.Agent("checkout", "production"))


@ls.traceable
def handle_order(order_id: str) -> dict:
    return {"order_id": order_id, "status": "charged"}


handle_order("A-1")
client.flush()
