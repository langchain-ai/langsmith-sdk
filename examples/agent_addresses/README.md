# Addressing runs to an agent

Send traces to an agent's environment with `Agent`, instead of naming a project.
Each file is one way to trace a run. Set `LANGSMITH_API_KEY` and
`LANGSMITH_TRACING=true` first.

## Python

| Example | Way of tracing |
|---------|----------------|
| [`traceable.py`](python/traceable.py) | `@traceable` decorator |
| [`langsmith_extra.py`](python/langsmith_extra.py) | `langsmith_extra` on a single call |
| [`tracing_context.py`](python/tracing_context.py) | `tracing_context` block |
| [`trace_context_manager.py`](python/trace_context_manager.py) | `trace` context manager |
| [`configure.py`](python/configure.py) | `ls.configure` for the whole process |
| [`env_vars.py`](python/env_vars.py) | `LANGSMITH_AGENT_ID` and `LANGSMITH_AGENT_ENVIRONMENT` |
| [`run_tree.py`](python/run_tree.py) | `RunTree` |
| [`create_run.py`](python/create_run.py) | `client.create_run` and `update_run` |
| [`query_agent_traces.py`](python/query_agent_traces.py) | Resolve an agent to its project, then query its runs |
| [`experiment_traces.py`](python/experiment_traces.py) | Run a dataset experiment, resolve it, query its runs |

## TypeScript

| Example | Way of tracing |
|---------|----------------|
| [`traceable.ts`](typescript/traceable.ts) | `traceable` |
| [`run_tree.ts`](typescript/run_tree.ts) | `RunTree` |
| [`create_run.ts`](typescript/create_run.ts) | `client.createRun` and `updateRun` |

Only an `Agent` can receive traces. `Experiment` and `Evaluator` addresses
name a project to query, and the query examples resolve them to a project id.
