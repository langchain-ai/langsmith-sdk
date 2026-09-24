"""2 · A parent run from headers: ambient, carried across services.

The upstream service's target travels in the `baggage` header, so the
downstream root joins the same target without naming one.
"""

import langsmith as ls

support_eu = ls.target("customer-support", environment="production", region="eu")


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


# Service A: start a trace and forward its headers.
with support_eu.trace("checkout") as upstream:
    headers = upstream.to_headers()

# Service B: adopt the parent from the incoming headers.
with ls.tracing_context(parent=headers):
    answer("hello")  # -> customer-support / production / eu

# Or per call.
answer("hello", langsmith_extra={"parent": headers})
