"""6 · Env vars: process-wide default from configuration.

No code at all. Every `Target` field has a `LANGSMITH_<FIELD>`
variable, derived from the field name:

    LANGSMITH_AGENT_ID=customer-support
    LANGSMITH_AGENT_ENVIRONMENT=production
    LANGSMITH_AGENT_REGION=eu            # optional

An incomplete set is warned about at client construction and ignored, so runs
go to the project instead.
"""

import langsmith as ls


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


print("from env:", ls.Target.from_env())  # noqa: T201
answer("hello")  # -> the env target, when nothing above names one
