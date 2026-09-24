# Target addressing examples (POC)

How a `Target` is built and used in each of the six ways a root run's destination is resolved. First match wins:

| # | Tier | File |
|---|---|---|
| 1 | Ambient | [`1_tracing_context.py`](1_tracing_context.py) |
| 2 | Ambient | [`2_distributed_parent.py`](2_distributed_parent.py) |
| 3 | Explicit | [`3_langsmith_extra.py`](3_langsmith_extra.py) |
| 4 | Explicit | [`4_traceable.py`](4_traceable.py) |
| 5 | Default | [`5_configure.py`](5_configure.py) |
| 6 | Default | [`6_env_vars.py`](6_env_vars.py) |

Below the root the target is inherited, never re-resolved ([`7_inheritance.py`](7_inheritance.py)). Write replicas fan one run out to several targets ([`8_replicas.py`](8_replicas.py)). The loose `agent_id` / `agent_environment` fields still work ([`9_loose_fields.py`](9_loose_fields.py)).

Each file runs on its own and sends traces to whatever `LANGSMITH_ENDPOINT` / `LANGSMITH_API_KEY` point at. `region` is not read by the backend yet.
