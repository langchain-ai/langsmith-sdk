"""4 · @traceable: explicit, at decoration time."""

import langsmith as ls

support = ls.address("customer-support", agent_environment="production")


@ls.traceable(address=support)
def classify(ticket: str) -> str:
    """Classify a ticket."""
    return "billing"


# Same thing, from the handle.
@support.traceable(run_type="llm")
def draft_reply(ticket: str) -> str:
    """Draft a reply to a ticket."""
    return "Thanks for reaching out."


classify("refund please")  # -> customer-support / production
draft_reply("refund please")  # -> customer-support / production

# An enclosing tracing_context still wins, as it does for project_name.
with support.with_agent_environment("staging").tracing_context():
    classify("refund please")  # -> customer-support / staging
