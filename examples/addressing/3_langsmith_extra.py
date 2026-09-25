"""3 · langsmith_extra: explicit, at call time.

Beats the decorator's own address, but loses to an enclosing
`tracing_context`.
"""

import langsmith as ls

support = ls.address("customer-support", agent_environment="production")
staging = support.with_agent_environment("staging")


@support.traceable
def answer(question: str) -> str:
    """Echo the question."""
    return f"echo: {question}"


answer("hello")  # -> customer-support / production
answer("hello", langsmith_extra={"address": staging})  # -> customer-support / staging
