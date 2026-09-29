"""4 · @traceable: explicit, at decoration time."""

import langsmith as ls

support = ls.address(agent_id="customer-support", agent_environment="production")


@ls.traceable(address=support)
def classify(ticket: str) -> str:
    """Classify a ticket."""
    return "billing"


classify("refund please")  # -> customer-support / production

# An enclosing tracing_context still wins, as it does for project_name.
with ls.tracing_context(address=support.with_agent_environment("staging")):
    classify("refund please")  # -> customer-support / staging
