"""Address a run you build by hand with `RunTree`.

Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true. Run it with `python run_tree.py`.
"""

import langsmith as ls

client = ls.Client()

run = ls.RunTree(
    name="handle_order",
    run_type="chain",
    inputs={"order_id": "A-1"},
    client=client,
    address=ls.Agent("checkout", "production"),
)
run.post()
run.end(outputs={"status": "charged"})
run.patch()
client.flush()
