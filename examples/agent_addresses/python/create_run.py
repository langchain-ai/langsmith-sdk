"""Address a run sent through the client with `create_run`.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python create_run.py`.
"""

import datetime
import uuid

import langsmith as ls

client = ls.Client()
agent = ls.Agent("checkout", "production")
run_id = uuid.uuid4()

client.create_run(
    id=run_id,
    name="handle_order",
    run_type="chain",
    inputs={"order_id": "A-1"},
    address=agent,
)
client.update_run(
    run_id,
    outputs={"status": "charged"},
    end_time=datetime.datetime.now(datetime.timezone.utc),
    address=agent,
)
client.flush()
