"""Addressing runs to a `Target`, in each of the six ways a root run is placed.

!!! warning "Experimental"
    Target addressing is a POC: in beta, enabled per workspace, and subject to
    change. `region` is not read by the backend yet.

A root run's destination is resolved once, at the trace root; the first match
wins, in this order:

    AMBIENT   1 · tracing_context(target=...)
              2 · a parent run from distributed-tracing headers
    EXPLICIT  3 · langsmith_extra={"target": ...}, at call time
              4 · @traceable(target=...), at decoration time
    DEFAULTS  5 · ls.configure(target=...)
              6 · LANGSMITH_TARGET_* env vars

Below the root the target is inherited, never re-resolved: child runs copy it,
and the `baggage` header carries it to other services. Write replicas fan one
run out to several targets.

Each section is independent. Nothing here needs a real workspace to read, but
running it sends traces to whatever LANGSMITH_ENDPOINT / LANGSMITH_API_KEY
point at.
"""

import langsmith as ls
from langsmith.run_trees import RunTree

# -- Building targets --------------------------------------------------------

# A target is one immutable value: an id and an environment, plus any optional
# dimension (here `region`). Validation happens here, not at ingest.
support = ls.target("customer-support", environment="production")
support_eu = ls.target("customer-support", environment="production", region="eu")

# Derive variants instead of repeating the id.
support_staging = support.with_environment("staging")


@ls.traceable
def answer(question: str) -> str:
    """Echo the question; names no destination of its own."""
    return f"echo: {question}"


# -- 1 · tracing_context: ambient, wins over everything below ----------------


def way_1_tracing_context() -> None:
    """Scope a block of code to a target.

    Sets the context variable, so it beats `langsmith_extra`, the decorator,
    `configure` and the env vars for every root run started inside it.
    """
    with ls.tracing_context(target=support_staging):
        answer("hello")  # -> customer-support / staging

    # Same thing, from the handle.
    with support_staging.tracing_context():
        answer("hello")  # -> customer-support / staging


# -- 2 · a parent run from headers: ambient, carried across services --------


def way_2_distributed_parent() -> None:
    """Continue a trace started in another service.

    The upstream service's target travels in the `baggage` header (as
    `langsmith-target=...`), so the downstream root joins the same target
    without naming one.
    """
    # Service A: start a trace and forward its headers.
    with support_eu.trace("checkout") as upstream:
        headers = upstream.to_headers()

    # Service B: adopt the parent from the incoming headers.
    with ls.tracing_context(parent=headers):
        answer("hello")  # -> customer-support / production / eu

    # Or per call.
    answer("hello", langsmith_extra={"parent": headers})


# -- 3 · langsmith_extra: explicit, at call time -----------------------------


def way_3_langsmith_extra() -> None:
    """Pick the target for one call of a traced function.

    Beats the decorator's own target, but loses to an enclosing
    `tracing_context`.
    """
    answer("hello", langsmith_extra={"target": support_staging})


# -- 4 · @traceable: explicit, at decoration time ----------------------------


@ls.traceable(target=support)
def classify(ticket: str) -> str:
    """Classify a ticket."""
    return "billing"


# Same thing, from the handle.
@support.traceable(run_type="llm")
def draft_reply(ticket: str) -> str:
    """Draft a reply to a ticket."""
    return "Thanks for reaching out."


def way_4_traceable() -> None:
    """Bind a target to a function when it is defined."""
    classify("refund please")  # -> customer-support / production
    draft_reply("refund please")  # -> customer-support / production

    # An enclosing tracing_context still wins, as it does for project_name.
    with support_staging.tracing_context():
        classify("refund please")  # -> customer-support / staging


# -- 5 · ls.configure: process-wide default in code --------------------------


def way_5_configure() -> None:
    """Set a default target for the whole process, once at startup."""
    ls.configure(target=support)
    try:
        answer("hello")  # -> customer-support / production
    finally:
        ls.configure(target=None)  # clear it again


# -- 6 · env vars: process-wide default from configuration -------------------

# No code at all. Every `Target` field has a `LANGSMITH_TARGET_<FIELD>`
# variable, derived from the field name:
#
#     LANGSMITH_TARGET_ID=customer-support
#     LANGSMITH_TARGET_ENVIRONMENT=production
#     LANGSMITH_TARGET_REGION=eu            # optional
#
# An incomplete set is warned about at client construction and ignored, so
# runs go to the project instead.


def way_6_env_vars() -> None:
    """Show the target the environment resolves to, if any."""
    print("from env:", ls.Target.from_env())  # noqa: T201
    answer("hello")  # -> the env target, when nothing above names one


# -- Inherit: below the root, the target is copied, never re-resolved -------


def inheritance() -> None:
    """Child runs keep their root's target, even under a new tracing_context."""

    @support.traceable
    def root() -> None:
        with support_staging.tracing_context():
            answer("child")  # still customer-support / production

    root()

    # Built by hand, a child copies its parent's target too.
    parent = RunTree(name="manual", target=support_eu)
    child = parent.create_child(name="step")
    assert child.target == support_eu


# -- Fan-out: write replicas send one run to several targets ----------------


def replicas() -> None:
    """Mirror each run to other targets, or to a project."""
    with ls.tracing_context(
        replicas=[
            support,  # a bare Target is a replica
            support_staging.replica(updates={"metadata": {"mirrored": True}}),
            {"project_name": "audit-log"},  # projects still work
        ]
    ):
        answer("hello")  # written three times


# -- Loose fields still work -------------------------------------------------


def loose_fields() -> None:
    """`agent_id` / `agent_environment` are folded into a Target on entry.

    A missing half is read from its env var; one still missing raises here
    instead of failing at ingest.
    """
    with ls.tracing_context(agent_id="customer-support", agent_environment="dev"):
        answer("hello")  # same as target=ls.target("customer-support", ...)


if __name__ == "__main__":
    for example in (
        way_1_tracing_context,
        way_2_distributed_parent,
        way_3_langsmith_extra,
        way_4_traceable,
        way_5_configure,
        way_6_env_vars,
        inheritance,
        replicas,
        loose_fields,
    ):
        example()
