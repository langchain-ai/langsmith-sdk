# What decides where a run lands

Every configuration that can set `session_name`, `agent_id` or
`agent_environment` on a run sent through `POST /runs/multipart`. The source of
truth is `run_helpers._setup_run` (the `@traceable` path),
`run_helpers._get_addressing` (the `trace()` path),
`run_trees._apply_agent_addressing`, `run_trees.RunTree.from_headers`, and
`Client.create_run` / `Client._apply_agent_addressing`.

Gates that only decide *whether* a run is sent -- `LANGSMITH_TRACING*`,
`LANGSMITH_TRACING_SAMPLING_RATE`, the OTel variables -- are out of scope.

A `TO-BE-FIXED` row is one that does not exist yet: the surface can name a
project but has no way to name an agent. Listed where it belongs so the gap
is visible while reading that surface; delete the row's tag once it works.

## Environment variables

| Var | Notes |
|---|---|
| `LANGSMITH_AGENT_ID` | `LANGSMITH_` only, no `LANGCHAIN_` alias. `lru_cache`d for the process. |
| `LANGSMITH_AGENT_ENVIRONMENT` | Same. Resolved independently of the id, so half a pair can come from the environment and half from code. |
| `HOSTED_LANGSERVE_PROJECT_NAME` | No prefix. Beats every other project variable. |
| `LANGSMITH_PROJECT` / `LANGCHAIN_PROJECT` | |
| `LANGSMITH_SESSION` / `LANGCHAIN_SESSION` | Legacy, lowest precedence. Falls back to `"default"`. |
| `LANGSMITH_RUNS_ENDPOINTS` | A JSON list of replicas. Each item may carry `project_name`. |
| `LANGSMITH_RUNS_ENDPOINTS` items' `agent_id` / `agent_environment` | TO-BE-FIXED: the parser drops both, though `WriteReplica` and baggage accept them. |
| `LANGSMITH_WORKSPACE_ID` / `LANGSMITH_TENANT_ID` | Not a destination, but picks the workspace, which decides whether agent addressing is enabled at all and which agent the key resolves to. |
| `LANGSMITH_CONFIG_FILE` / `LANGSMITH_PROFILE` | `~/.langsmith/config.json`. A profile carries `api_url`, `api_key` and `workspace_id` -- never a project or an agent. |

There is no `project_id` or `session_id` environment variable anywhere in the
Python SDK: the only project-shaped names read are the five above.
`LANGSMITH_EXPERIMENT` names the project for `ls.testing` test suites, not for
`@traceable`.

## `@traceable(...)` decorator arguments

| Arg | Effect |
|---|---|
| `project_name` | Explicit project. Loses to the context var and to the parent run. |
| `client` | Which client flushes. `Client` itself carries no addressing. |
| `agent_id` / `agent_environment` | TO-BE-FIXED: not accepted. Today the only way to address a `@traceable` run to an agent in code is `tracing_context` or a parent that is already addressed. |

## Invocation-time `langsmith_extra={...}`

| Key | Effect |
|---|---|
| `project_name` | Explicit project, beats the decorator's. |
| `parent` | A `RunTree` hands down its `session_name` / `agent_id` / `agent_environment`. A dotted-order `str` is a placeholder parent with no addressing. A `Mapping` goes through `from_headers`, below. |
| `run_tree` | Deprecated alias of `parent`. |
| `replicas` | Per-replica addressing, below. |
| `client` | As above. |
| `config` | An ordinary kwarg, not part of `langsmith_extra`: a LangChain `RunnableConfig` becomes the parent through `RunTree.from_runnable_config`, carrying the LangChain tracer's project. |
| `agent_id` / `agent_environment` | TO-BE-FIXED: not accepted. |
| `config` carrying an agent | TO-BE-FIXED: `RunTree.from_runnable_config` reads the LangChain tracer's project only, so a LangChain parent can never hand down an agent. |

## Context and globals

| Source | Sets |
|---|---|
| `tracing_context(project_name=, agent_id=, agent_environment=, parent=, replicas=, client=)` | The `_PROJECT_NAME`, `_AGENT_ID`, `_AGENT_ENVIRONMENT` and `_REPLICAS` context vars. Raises `LangSmithUserError` when a project and an agent are passed in the same call. |
| `ls.configure(project_name=)` | `_PROJECT_NAME` and `_GLOBAL_PROJECT_NAME`. |
| `ls.configure(agent_id=, agent_environment=)` | TO-BE-FIXED: no agent parameter, so a process-wide agent can only come from the environment. |
| An enclosing `@traceable` | Its own `_setup_run` sets all three context vars for its children. |
| An enclosing `with trace(project_name=, parent=)` | The same context vars, resolved by `_get_addressing` rather than `_setup_run`. |
| `with trace(agent_id=, agent_environment=)` | TO-BE-FIXED: not accepted, the same gap as `@traceable`. |
| A parent `RunTree`, through `create_child` | Copies `session_name`, `agent_id` and `agent_environment` verbatim. |

## Replicas

`WriteReplica` keys that matter: `project_name`, `agent_id`,
`agent_environment`, `client`, `primary`, `updates`.

`RunTree._replica_addressing` applies the usual precedence per replica: its own
`project_name` wins, and raises if an agent is named beside it; then its own
agent; then it inherits the run tree's addressing whole, never mixing the two.

Sources: `langsmith_extra["replicas"]`, `tracing_context(replicas=)`,
`LANGSMITH_RUNS_ENDPOINTS`, and the `langsmith-replicas` baggage entry.

## Distributed tracing headers

`parent=headers` reads `langsmith-trace` for the dotted order, then `baggage`
for `langsmith-project`, `langsmith-agent-id`,
`langsmith-agent-environment` and `langsmith-replicas`.

`RunTree.from_headers` resolves them as follows.

- A baggage project beats a project the caller named.
- An agent the caller named beats a baggage project, with a warning.
- A project or agent the caller named silences a baggage agent.
- A baggage agent applies only with both halves present; half a pair is dropped
  with a warning, since baggage is untrusted and must not raise.

## Direct `RunTree(...)` and `Client.create_run(...)`

Both take `project_name` / `session_name` / `project_id` / `session_id` and
`agent_id` / `agent_environment`. Both raise on a project and an agent in the
same call, then fill a missing agent half from the environment when no project
is named. `Client._apply_agent_addressing` re-reads the environment on posts,
but not on patches.

## Resolution order for a `@traceable` root run

From `run_helpers._setup_run`:

```
explicit_project = _PROJECT_NAME cv          # outer traceable / tracing_context / configure
                or parent_run.session_name
                or langsmith_extra["project_name"]
                or @traceable(project_name=)
                or _GLOBAL_PROJECT_NAME
agent_id        = _AGENT_ID cv or parent_run.agent_id or LANGSMITH_AGENT_ID
agent_env       = _AGENT_ENVIRONMENT cv or parent_run.agent_environment or LANGSMITH_AGENT_ENVIRONMENT

if explicit_project is None and agent_id:  agent-addressed, no project
else:                                      project = explicit_project or get_tracer_project()
                                           agent pair dropped, silently
```

The `RunTree` validator then re-runs `resolve_agent_addressing` against the
environment, and `Client.create_run` runs `_reject_conflicting_addressing`
followed by its own `_apply_agent_addressing`.

## OTel span attributes

Out of scope for multipart, listed because the gap is the same shape.

| Attribute | Effect |
|---|---|
| `langsmith.trace.session_name` / `langsmith.trace.session_id` | Written from the run's `session_name` / `session_id`; the receiver routes the span by them. |
| `langsmith.trace.agent_id` / `langsmith.trace.agent_environment` | TO-BE-FIXED: no such attribute, so an agent-addressed run exported through OTel carries no addressing at all -- the same silent fallback the `TEMPORARY` test pins for `POST /runs`. |

The `LANGSMITH_SESSION_ID` / `LANGSMITH_SESSION_NAME` constants in
`_internal/otel/_otel_exporter.py` hold these attribute keys. They are not
environment variables, despite the names.

## Inconsistencies to pin with a case each

1. With only `LANGSMITH_AGENT_ENVIRONMENT` set, `_setup_run` tests
   `selected_agent_id` alone and falls back to `default` in silence, while
   `trace()` and `RunTree` use `is_agent_addressed`, which accepts either half,
   and send the run for the endpoint to refuse with a 400. One configuration,
   two outcomes, decided by the entry point.
2. `@traceable(project_name=X)` inside `tracing_context(agent_id=A)`: no
   conflict check spans the two, so the project wins and the agent is dropped
   without a word. The same holds for `langsmith_extra={"project_name"}` inside
   `tracing_context(agent_id=)`, and for `ls.configure(project_name=)` beside
   an agent in the environment.
3. `LANGSMITH_PROJECT` beside `LANGSMITH_AGENT_ID`: the bug already pinned in
   `test_create_update_run.py`, reachable from this path too. An environment
   project is not "explicit", so the agent wins.
4. A child of an agent-addressed root that passes
   `langsmith_extra={"project_name": ...}` lands in that project, because the
   inherited context var is `None` and the inner explicit project wins over the
   inherited agent. Intended or not, it should be pinned.
5. `trace()` and `@traceable` resolve through two different functions, so every
   case worth having should run through both.
