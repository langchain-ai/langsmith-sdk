"""5 · ls.configure: process-wide default in code, once at startup."""

import langsmith as ls

ls.configure(address=ls.address("customer-support", agent_environment="production"))


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


answer("hello")  # -> customer-support / production

ls.configure(address=None)  # clear it again
