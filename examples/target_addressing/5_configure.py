"""5 · ls.configure: process-wide default in code, once at startup."""

import langsmith as ls

ls.configure(target=ls.target("customer-support", environment="production"))


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


answer("hello")  # -> customer-support / production

ls.configure(target=None)  # clear it again
