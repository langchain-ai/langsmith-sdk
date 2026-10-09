"""Address every traced call with environment variables.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python env_vars.py`.
"""

import os

# Normally set in your shell or deployment. Set both before the SDK reads them.
os.environ["LANGSMITH_AGENT_ID"] = "checkout"
os.environ["LANGSMITH_AGENT_ENVIRONMENT"] = "production"

import langsmith as ls  # noqa: E402

client = ls.Client()


@ls.traceable(client=client)
def handle_order(order_id: str) -> dict:
    return {"order_id": order_id, "status": "charged"}


handle_order("A-1")
client.flush()
