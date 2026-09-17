# Agent addressing integration tests

End-to-end tests for addressing a run by agent instead of by project, against a
real LangSmith backend.

Design doc: [POST /api/v1/runs/multipart](https://app.notion.com/p/3d7808527b178194bcd6d441bac8e2ba).
The wire shape is flat `agent_id` / `agent_environment`, and only
`POST /runs/multipart` reads it.

## Principles

- One file per SDK method. The SDK resolves addressing in three separate
  places, so a case failing in one file but not another names the broken one.
- Only what the SDK can send. Endpoint-contract cases belong in langchainplus.
- Every case: configure, send, assert which project the run landed in.
- Fresh agent key and project name per run.

## Running them

```bash
cd python && env LANGSMITH_ENDPOINT=<endpoint> LANGSMITH_API_KEY=<key> LANGSMITH_WORKSPACE_ID=<workspace-id> uv run python -m pytest tests/integration_tests/agent_addressing -v
```

## FAQ

- **A test fails. Is that expected?** A few do, on purpose. Each one's comment
  starts with `KNOWN FAILURE` and says which bug it pins. Nothing else should
  fail.
- **Why won't it run against production?** Every test creates an agent and
  four tracing projects. Use dev or a local LangSmith.
- **Does it clean up after itself?** It tries, and logs what it cannot remove.
  Deleting an agent only archives it until langchainplus#38785 ships, so its
  projects stay behind until then. No flag to flip once that lands.
- **Why does every run set `trace_id` and `dotted_order`?** Without both,
  `create_run` uses `POST /runs` instead of multipart. That endpoint ignores
  the agent fields, so the run lands in `default` with no error.
- **Why compare `session_id` instead of reading the run out of the expected
  project?** `read_run` ignores `project_id` on ClickHouse-backed deployments,
  so scoping the read proves nothing.
- **Why is one test mocked, in an integration suite?** `test_rollout_disabled.py`
  stubs the 403 a workspace off the `agent_platform_unified_experience` flag
  gets. A workspace with the flag on cannot produce one, and a second flag-off
  workspace would mean a second API key in CI. It asserts the SDK's side only.
- **Why does the agent lookup build its own URL?** `/agents` exists only under
  `/api/v1`, and the SDK has no agent methods yet. See the TODO.

## TODO

- **Fix the SDK**: `LANGSMITH_PROJECT` plus `LANGSMITH_AGENT_ID` should get a
  400, not silently pick the agent. One test pins today's behavior.
- **Bring back `test_create_feedback.py`**, removed on 2026-09-17. It had five
  cases and passed. Two questions first: does `create_feedback` read the agent
  env vars, and does a resolved pair actually decide where feedback is written?
  The second matters because on SmithDB-only the run cannot be looked up, which
  is the whole reason the pair exists there.
- **Delete the `TEMPORARY` test** in `test_create_update_run.py` once the
  non-multipart endpoints read the agent pair.
- **Use SDK methods for the agent API** once they exist, replacing
  `Harness.agents_url` and its hand-built `/api/v1` prefix. These routes are
  `x-internal`, so they may never be public; the suite then needs another way
  to read back where a run landed.
- **Decide whether `@traceable(agent_id=, agent_environment=)` is wanted.**
  `decorator_agent` in `test_traceable.py` assumes yes; delete it if not.
- **Add the missing files**: `test_trace.py`, `test_run_tree.py` (including
  replicas and the baggage hop), `test_legacy_endpoints.py`. Then cassettes
  and a cross-check of the langchainplus Go tests. For the baggage hop: on the
  `@traceable` path `_get_parent_run` always hands `from_headers` a project,
  defaulting to `default`, so a baggage agent is always ignored there.
