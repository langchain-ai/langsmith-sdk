---
type: repository quickstart
title: LangSmith SDK Repository Quickstart
description: Task-oriented routing map for the independently implemented Python and JavaScript/TypeScript LangSmith SDKs, their public surfaces, major workflows, ownership boundaries, and safe validation paths.
tags: [quickstart, sdk, python, javascript, typescript, tracing, evaluation, sandbox, development]
verified:
  - by: openwiki/0.5.2
    at: 2026-09-28T08:35:15.620Z
sources:
  - id: openwiki-source-b2d60e3aedc0d5c768840e9a
    resource: repo://.github/workflows/protect-openapi-client.yml
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-f317ee207e1653d2033c81a4
    resource: repo://CONTRIBUTING.md
  - id: openwiki-source-1278717ecdbca75bfb2a542f
    resource: repo://js/AGENTS.md
  - id: openwiki-source-800d5dde6ae372323c1d8246
    resource: repo://js/README.md
  - id: openwiki-source-8417e31aa1fddf53964ceb5a
    resource: repo://js/scripts/create-entrypoints.js
  - id: openwiki-source-c27c18f68326f94a1c4b2695
    resource: repo://js/src/client.ts
  - id: openwiki-source-0e0490f13c99adb166de7c53
    resource: repo://js/src/index.ts
  - id: openwiki-source-c1a0aa1d1779b0abb40046c0
    resource: repo://js/src/sandbox/sandbox.ts
  - id: openwiki-source-e67ba2efb94e620c92d92b92
    resource: repo://js/src/utils/env.ts
  - id: openwiki-source-9d11c849d0c541bb26055d77
    resource: repo://python/AGENTS.md
  - id: openwiki-source-e1498332cfe4ae0889c8c3ac
    resource: repo://python/langsmith/__init__.py
  - id: openwiki-source-197446e566d18b5ec23537cc
    resource: repo://python/langsmith/client.py
  - id: openwiki-source-923dd73ee83ba4b6c0554733
    resource: repo://python/langsmith/run_helpers.py
  - id: openwiki-source-b880125d71a73ecc7ad6e755
    resource: repo://python/langsmith/sandbox/_sandbox.py
  - id: openwiki-source-26a7d4052cb10f44c697ef05
    resource: repo://python/langsmith/sandbox/_sse_execute.py
  - id: openwiki-source-e8ccc4222c6775a30580b26e
    resource: repo://python/pyproject.toml
  - id: openwiki-source-18f88568abbfc5332724cfc8
    resource: repo://python/README.md
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "openwiki/0.5.2", at: "2026-09-28T08:35:15.620Z" }
---

# LangSmith SDK Repository Quickstart

This repository owns two independent `langsmith` SDK implementations for the same observability and evaluation platform: Python under `python/` and JavaScript/TypeScript under `js/`. They share product concepts, not runtime code or a guaranteed one-to-one API shape. For a cross-SDK change, verify naming, behavior, lifecycle, and tests in both languages.

Java and Go are outside this repository: use [langchain-ai/langsmith-java](https://github.com/langchain-ai/langsmith-java) and [langchain-ai/langsmith-go](https://github.com/langchain-ai/langsmith-go). Scope implementation and local validation here to Python and JavaScript/TypeScript.

> **Authority rule:** current source and focused tests are authoritative. The pages below are just-in-time navigation aids, not substitutes for reading the changed implementation and its tests.

## Route by task

Choose the user-visible contract first, then the language. Do not start by copying the other SDK's file layout.

| Task | First boundary to inspect | Detailed route |
|---|---|---|
| Public imports, package layers, sync/async differences, or parity | Python `langsmith/__init__.py`; TypeScript root and subpath exports | [Dual-SDK Architecture and Public Surfaces](/openwiki/architecture/sdk-architecture.md) |
| Endpoint, API key, workspace, profile, OAuth, headers, retries, or browser behavior | The relevant handwritten client constructor and configuration helpers | [Client Configuration, Endpoints, and Authentication](/openwiki/concepts/client-configuration-and-auth.md) |
| Runs, projects, agents, datasets, examples, feedback, experiments, queues, prompts, sharing, or threads | The handwritten platform client and any generated-resource bridge | [LangSmith Platform Client Domains](/openwiki/concepts/platform-client.md) |
| Run identity, parent/child nesting, distributed propagation, completion, replicas, or project/agent destination | `RunTree`, tracing context, and addressing validation | [Run Trees, Trace Identity, and Context Propagation](/openwiki/concepts/run-tree-and-context.md) |
| Sampling, privacy transforms, batching, compression, retries, replicas, flush, shutdown, or dropped traces | Follow capture from `traceable`/`RunTree` into client ingestion | [Trace Capture, Transformation, and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md) |
| Ingestion timing, call count, wire size, or application-thread occupancy | Compare the trace lab's direct, batched, multipart, compressed, OTEL, and hybrid paths | [Measured Trace Ingestion Paths](/openwiki/workflows/trace-ingestion-measured.md) |
| Dataset evaluation, experiment execution, concurrency, repetitions, comparative evaluation, or evaluator tracing | The language's evaluation entrypoint and runner | [Evaluation and Experiment Workflows](/openwiki/workflows/evaluation-and-experiments.md) |
| Pytest, Jest, or Vitest tracking and assertions | The adapter plus plugin/reporter lifecycle | [LangSmith Test Tracking and Evaluation Assertions](/openwiki/testing/test-tracking-and-assertions.md) |
| Provider, agent, realtime/voice, LangChain, or OpenTelemetry integration | The wrapper/integration, normalization boundary, and focused tests | [Provider Wrappers, Agent Integrations, and OpenTelemetry](/openwiki/integrations/provider-wrappers-and-opentelemetry.md) |
| Sandbox lifecycle, files, services, mounts, proxy auth, command streaming, reconnect, or cleanup | `langsmith.sandbox` or `langsmith/sandbox`, then control-plane and dataplane calls | [Sandbox Lifecycle, Files, Services, and Command Execution](/openwiki/workflows/sandbox-lifecycle-and-execution.md) |
| Test choice or CI diagnosis | The narrowest offline test proving the changed contract | [Repository Test Strategy and Safe Validation](/openwiki/testing/repository-test-strategy.md) |
| Build, package entrypoint, generated API, staging mirror, or release | Repository scripts and protected workflows | [Development, Generated Code, Builds, and Releases](/openwiki/operations/development-and-release.md) |

## Public entrypoints and important asymmetries

### Python

`python/langsmith/__init__.py` is a curated lazy facade: module `__getattr__` resolves public names and `__all__` records the root surface. It includes `Client`, `AsyncClient`, `TracingMode`, `RunTree`, tracing helpers, sync and async evaluation functions, test helpers, caches, secrets, UUID helpers, and stable exception exports. Follow each lazy import to its owning module before changing behavior.

Python deliberately has separate synchronous and asynchronous clients; do not assume `Client` and `AsyncClient` are exact mirrors. The package uses Hatchling, requires Python 3.10 or later, and registers the `langsmith_plugin` pytest plugin.

### TypeScript / JavaScript

`js/src/index.ts` keeps the package root comparatively small: `Client`, selected schemas, `RunTree`, fetch/project/UUID utilities, prompt-cache APIs, generated error classes, and version metadata. Major capabilities live at public subpaths, notably `langsmith/traceable`, `langsmith/evaluation`, `langsmith/wrappers`, `langsmith/jest`, `langsmith/vitest`, `langsmith/sandbox`, and `langsmith/experimental/otel/*`.

`js/scripts/create-entrypoints.js` is the subpath registry. The build uses it to generate aligned ESM, CommonJS, and declaration shims and to synchronize `package.json` `exports` and `files`. Change the registry and rebuild rather than maintaining one module format by hand.

### Runtime choices that are not identical

- **Tracing modes:** Python accepts per-client `"langsmith"`, `"otel"`, and `"hybrid"`; TypeScript accepts `"langsmith"` and `"otel"`. Both resolve explicit client configuration before `LANGSMITH_TRACING_MODE` and legacy OpenTelemetry flags. Route delivery and teardown changes through the tracing and integration pages rather than assuming mode parity.
- **Agent addressing:** Python's tracing context and run APIs currently expose beta `agent_id`/`agent_environment` addressing as an alternative to a project. Project and agent destinations conflict; unsupported workspaces reject agent-addressed runs instead of silently falling back to a project. Treat this as a Python-specific, workspace-gated contract unless current TypeScript source proves otherwise.
- **Sandbox command transports:** Python normally uses WebSocket execution, with feature-selected SSE as a one-way streaming alternative; SSE cannot provide PTY, live stdin, or signal controls. TypeScript uses WebSocket for streaming/non-blocking execution and falls back to blocking HTTP only for the simple waiting path when the optional `ws` package is unavailable. Transport-sensitive changes require focused reconnect, timeout, and control-channel tests in the affected SDK.

## Generated and handwritten ownership

The following trees are generated from the LangSmith OpenAPI contract through Stainless:

- `python/langsmith/_openapi_client/`
- `js/src/_openapi_client/`

**Never edit them manually.** Authorized changes arrive through the external synchronization workflow, and repository CI blocks ordinary pull requests that touch them. Endpoint policy, compatibility, tracing, orchestration, and configuration adaptation belong in handwritten code outside these trees; contract changes belong in the upstream OpenAPI/Stainless process.

The handwritten clients are composition boundaries. They preserve established configuration and tracing behavior while exposing selected generated resources. When bridging a resource, verify base-URL normalization, credentials/workspace headers, timeout and custom transport behavior, backend compatibility, and public typing—not only the generated method.

Generated package artifacts are separate: TypeScript root shims and `dist/` are rebuilt from scripts, while Python tooling exclusions for generated diagnostics are ownership signals, not permission to patch generated output.

## Safest validation path

Work from the SDK directory. Start with the smallest offline unit test that proves the changed behavior, then run the complete baseline for each SDK touched.

```bash
cd python
TEST=tests/unit_tests/test_client.py make tests
make format
make lint
make tests
```

```bash
cd js
NODE_OPTIONS=--experimental-vm-modules npx jest src/tests/context.test.ts
pnpm format
pnpm lint
pnpm test
```

Escalate only for the boundary changed: use credentialed integration tests for deployed API/provider behavior, `make test-wheel-imports` for Python packaging and runtime dependencies, and `pnpm build` plus the relevant export/environment suite for TypeScript declarations, ESM/CJS, browser, or bundler behavior. Preserve full failure output; do not weaken network isolation merely to make an offline test pass.

## Release boundary

Python and TypeScript have independent versions and publication workflows. Follow only the **Cutting a release** procedure in `CONTRIBUTING.md`: create separate version-bump pull requests against `main`, use `uv run bump2version` for Python or `pnpm run bump-version` for TypeScript, and do not hand-edit version files, publish locally, or push release tags. See [Development, Generated Code, Builds, and Releases](/openwiki/operations/development-and-release.md) before release work.
