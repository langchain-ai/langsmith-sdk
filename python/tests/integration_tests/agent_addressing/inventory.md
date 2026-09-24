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
| `agent_id` / `agent_environment` | Explicit agent, at the same tier as `project_name`. |

## Invocation-time `langsmith_extra={...}`

| Key | Effect |
|---|---|
| `project_name` | Explicit project, beats the decorator's. |
| `parent` | A `RunTree` hands down its `session_name` / `agent_id` / `agent_environment`. A dotted-order `str` is a placeholder parent with no addressing. A `Mapping` goes through `from_headers`, below. |
| `run_tree` | Deprecated alias of `parent`. |
| `replicas` | Per-replica addressing, below. |
| `client` | As above. |
| `config` | An ordinary kwarg, not part of `langsmith_extra`: a LangChain `RunnableConfig` becomes the parent through `RunTree.from_runnable_config`, carrying the LangChain tracer's project. |
| `agent_id` / `agent_environment` | Explicit agent, at the same tier as `project_name`. |
| `config` carrying an agent | TO-BE-FIXED: `RunTree.from_runnable_config` reads the LangChain tracer's project only, so a LangChain parent can never hand down an agent. |

## Context and globals

| Source | Sets |
|---|---|
| `tracing_context(project_name=, agent_id=, agent_environment=, parent=, replicas=, client=)` | The `_PROJECT_NAME`, `_AGENT_ID`, `_AGENT_ENVIRONMENT` and `_REPLICAS` context vars. Raises `LangSmithUserError` when a project and an agent are passed in the same call. |
| `ls.configure(project_name=)` | `_PROJECT_NAME` and `_GLOBAL_PROJECT_NAME`. |
| `ls.configure(agent_id=, agent_environment=)` | `_GLOBAL_AGENT_ID` / `_GLOBAL_AGENT_ENVIRONMENT`, the same tier as its `project_name`. |
| An enclosing `@traceable` | Its own `_setup_run` sets all three context vars for its children. |
| An enclosing `with trace(project_name=, parent=)` | The same context vars, resolved by `_get_addressing` rather than `_setup_run`. |
| `with trace(agent_id=, agent_environment=)` | The same context vars, resolved by `_get_addressing`. |
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
project   = _PROJECT_NAME cv or parent.session_name or langsmith_extra["project_name"]
            or @traceable(project_name=) or _GLOBAL_PROJECT_NAME
agent_id  = _AGENT_ID cv or parent.agent_id or langsmith_extra["agent_id"]
            or @traceable(agent_id=) or _GLOBAL_AGENT_ID
agent_env = the same chain for the environment

utils.resolve_addressing(project, agent_id, agent_env):
  project named in code           -> project alone, whatever tier the agent came from
  agent named in code             -> agent alone, half a pair completed from the env
  agent in the env only           -> agent, plus any *configured* env project (not "default")
                                     so the endpoint answers 400 on the pair
  nothing                         -> get_tracer_project()
```

Each chain picks its own winner before `resolve_addressing` compares them, so a
project always beats an agent named in code, whichever tier each came from.
The `RunTree` validator keeps values that already carry an agent and completes
a half pair from the environment; `Client.create_run` rejects a project and an
agent named in the same call, then `_apply_agent_addressing` forwards whatever
travels together.

## OTel span attributes

Out of scope for multipart, listed because the gap is the same shape.

| Attribute | Effect |
|---|---|
| `langsmith.trace.session_name` / `langsmith.trace.session_id` | Written from the run's `session_name` / `session_id`; the receiver routes the span by them. |
| `langsmith.trace.agent_id` / `langsmith.trace.agent_environment` | TO-BE-FIXED: no such attribute, so an agent-addressed run exported through OTel carries no addressing at all -- the same silent fallback the `TEMPORARY` test pins for `POST /runs`. |

The `LANGSMITH_SESSION_ID` / `LANGSMITH_SESSION_NAME` constants in
`_internal/otel/_otel_exporter.py` hold these attribute keys. They are not
environment variables, despite the names.

## Inconsistencies, each pinned by a case

1. `@traceable(project_name=X)` inside `tracing_context(agent_id=A)`: the
   project wins whatever tier each came from, because each chain is resolved
   on its own first. Commit `6157cfbc` says the higher tier wins; the code is
   right and the message is wrong, since `evaluate()` names its experiment on
   the call and must keep working under an ambient agent.
   `context_agent_and_decorator_project`, `test_evaluate.py`.
2. A child joins its parent's trace whatever it names: `create_child` copies
   the parent's addressing and ignores what `_setup_run` resolved for the
   child. `child_of_agent_root_with_extra_project`.
3. `trace()` and `@traceable` resolve through two different functions, so every
   case worth having should run through both.
4. `_get_parent_run` hands `from_headers` and `from_dotted_order` a
   `project_name` that defaults to `"default"`, so on the `@traceable` path a
   baggage agent is always ignored and a dotted-order parent drops an env
   agent in silence. Not yet pinned: distributed tracing is a later file.

Fixed since first written, kept green by a case each: a lone
`LANGSMITH_AGENT_ENVIRONMENT` reaching the endpoint (`env_environment_only`),
an env project beside an env agent travelling together
(`env_agent_and_env_project`, `env_agent_and_hosted_project`), and the
decorator's agent arguments (`decorator_agent`).
