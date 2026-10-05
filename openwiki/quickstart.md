---
type: repository quickstart
title: LangSmith SDK Repository Quickstart
description: Task-oriented entry map for engineers changing the independently implemented Python and JavaScript/TypeScript LangSmith SDKs, their public surfaces, runtime workflows, generated-code boundary, and validation loop.
tags: [quickstart, sdk, python, javascript, typescript, tracing, evaluation, testing, release]
verified:
  - by: openwiki/0.5.2
    at: 2026-10-05T08:37:48.776Z
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
  - id: openwiki-source-9d11c849d0c541bb26055d77
    resource: repo://python/AGENTS.md
  - id: openwiki-source-e1498332cfe4ae0889c8c3ac
    resource: repo://python/langsmith/__init__.py
  - id: openwiki-source-197446e566d18b5ec23537cc
    resource: repo://python/langsmith/client.py
  - id: openwiki-source-18f88568abbfc5332724cfc8
    resource: repo://python/README.md
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "openwiki/0.5.2", at: "2026-10-05T08:37:48.776Z" }
---

# LangSmith SDK Repository Quickstart

This repository owns two independent `langsmith` implementations for the same LangSmith observability and evaluation platform: Python under `python/` and JavaScript/TypeScript under `js/`. They cover parallel product concepts, but neither is a binding over shared runtime code and their APIs and lifecycles are not necessarily identical. For a cross-SDK change, verify behavior and tests in both languages rather than mechanically mirroring files.

Java and Go SDKs are maintained in the external [langsmith-java](https://github.com/langchain-ai/langsmith-java) and [langsmith-go](https://github.com/langchain-ai/langsmith-go) repositories. This repository's implementation and local validation authority extends only to Python and JavaScript/TypeScript.

> **Authority rule:** source and tests are authoritative. Use the pages below as just-in-time maps, then check the current implementation and focused tests.

## Route the task first

Choose the user-visible contract first, then choose the language implementation. In particular, Python has distinct synchronous and asynchronous clients, while TypeScript uses promise-based methods on its principal `Client`.

| Task | Start at | Owning page |
|---|---|---|
| Understand layers, public imports, sync/async differences, or parity | Python `langsmith/__init__.py`; TypeScript root and subpath exports | [Dual-SDK Architecture and Public Surfaces](/openwiki/architecture/sdk-architecture.md) |
| Change endpoint, API key, workspace, profile, headers, retry, timeout, OAuth, or browser behavior | Handwritten client constructor and configuration helpers | [Client Configuration, Endpoints, and Authentication](/openwiki/concepts/client-configuration-and-auth.md) |
| Change runs/projects, datasets/examples, feedback, experiments, queues, prompts, sharing, or threads | Public handwritten client and its generated-resource bridge | [LangSmith Platform Client Domains](/openwiki/concepts/platform-client.md) |
| Change run identity, nesting, propagation, rerooting, tags, metadata, replicas, or completion | `RunTree` and tracing-context helpers | [Run Trees, Trace Identity, and Context Propagation](/openwiki/concepts/run-tree-and-context.md) |
| Change trace capture, privacy, sampling, queues, batching, compression, retry, failure persistence, flush, or shutdown | Follow capture through `RunTree` into ingestion | [Trace Capture, Transformation, and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md) |
| Compare durable measurements of direct, batched, multipart, compressed, OTEL, or hybrid ingestion | Trace-lab cases and recorded measurements | [Measured Trace Ingestion Paths](/openwiki/workflows/trace-ingestion-measured.md) |
| Change evaluation, experiment execution, concurrency, repetitions, evaluators, or result consumption | Language-specific evaluation entrypoint and runner | [Evaluation and Experiment Workflows](/openwiki/workflows/evaluation-and-experiments.md) |
| Change pytest, Jest, or Vitest tracking and assertions | Framework adapter and reporter/plugin lifecycle | [LangSmith Test Tracking and Evaluation Assertions](/openwiki/testing/test-tracking-and-assertions.md) |
| Add or repair a provider, agent, realtime, LangChain, or OpenTelemetry integration | Matching wrapper/integration and focused tests | [Provider Wrappers, Agent Integrations, and OpenTelemetry](/openwiki/integrations/provider-wrappers-and-opentelemetry.md) |
| Change sandbox creation, readiness, services, files, mounts, proxies, commands, reconnect, or cleanup | Public sandbox client/handle and transport boundary | [Sandbox Lifecycle, Access, Services, and Command Execution](/openwiki/workflows/sandbox-lifecycle-and-execution.md) |
| Choose tests or diagnose CI/package compatibility | Narrowest test proving the changed contract | [Repository Test Strategy and Safe Validation](/openwiki/testing/repository-test-strategy.md) |
| Build, add an entrypoint, update generated APIs, or release | Repository scripts and protected workflows | [Development, Generated Code, Builds, and Releases](/openwiki/operations/development-and-release.md) |

The two ingestion pages serve different purposes: **Trace Capture, Transformation, and Ingestion** is the implementation and control-flow guide; **Measured Trace Ingestion Paths** is the durable trace-lab companion for empirical timing, call-count, wire-size, and application-thread comparisons. Do not substitute one for the other.

## Public entrypoints and ownership

### Python

`python/langsmith/__init__.py` is a curated lazy facade. Its module `__getattr__` imports root-level APIs on demand, while `__all__` records the supported root names. The facade includes:

- `Client`, `AsyncClient`, `TracingMode`, `RunTree`, and tracing-context helpers;
- sync and async evaluation functions plus testing helpers;
- the `address` module and `Address` type;
- prompt cache interfaces and global cache configuration;
- UUID helpers, secrets, runtime overrides, and stable generated exception classes.

Follow each lazy branch to its owning handwritten module before changing behavior. `Client` is the mature synchronous and tracing-oriented surface; `AsyncClient` owns asynchronous HTTP/lifecycle behavior and is not an exact mirror. Python is built with Hatchling, requires Python 3.10 or later, and registers `langsmith_plugin` as a pytest plugin.

### TypeScript / JavaScript

`js/src/index.ts` intentionally defines a compact root. It exports `Client` and selected schema types, `RunTree`, address construction and `EnvAddressError`, fetch/project helpers, cache and UUID utilities, tracing guards, generated API error classes, and version metadata.

Broader APIs are package subpaths registered in `js/scripts/create-entrypoints.js`, including `langsmith/client`, `langsmith/traceable`, `langsmith/evaluation`, `langsmith/jest`, `langsmith/vitest`, `langsmith/wrappers` and provider-specific wrappers, experimental OpenTelemetry entrypoints, and both `langsmith/sandbox` and its experimental compatibility path. The registry generates matching ESM, CommonJS, and declaration shims, then synchronizes `package.json` `exports` and `files`. Add or change a public subpath in the registry and rebuild; do not maintain one module format or package manifest entry by hand.

## Never hand-edit generated OpenAPI trees

The Stainless-generated OpenAPI clients are:

- `python/langsmith/_openapi_client/`
- `js/src/_openapi_client/`

**Never edit either tree manually.** Generated updates arrive through the authorized external synchronization workflow, and repository CI rejects ordinary pull requests touching these paths. Endpoint/resource contract changes belong in the upstream OpenAPI/Stainless process. Put configuration adaptation, tracing policy, compatibility, orchestration, and higher-level behavior in handwritten code outside these trees.

The handwritten clients are the composition boundary. When exposing a generated resource through one, verify URL construction, API key and workspace headers, timeout and transport behavior, backend compatibility, and public typing—not only the generated method. A root export of a generated error does not transfer ownership of that class to handwritten code.

TypeScript build output is a different kind of generated artifact: `dist/` and root ESM/CJS/declaration shims are recreated by `pnpm build`. In Python, tooling exclusions for `_openapi_client` mark the same ownership boundary; they are not permission to patch generated output.

## Safe local change loop

Work from the SDK directory. Start with the narrowest offline test, then run the baseline for every SDK touched.

Python focused test and baseline:

```bash
cd python
TEST=tests/unit_tests/test_client.py make tests
make format
make lint
make tests
```

`make tests` runs through the managed `uv` environment, removes tracing credentials from the test process, and disables network sockets. Do not weaken that isolation merely to make a unit test pass.

TypeScript focused test and baseline:

```bash
cd js
NODE_OPTIONS=--experimental-vm-modules npx jest src/tests/context.test.ts
pnpm format
pnpm lint
pnpm test
```

Escalate only for the changed boundary: use credentialed integration suites for deployed API/provider behavior, `make test-wheel-imports` for Python wheel/runtime-dependency checks, and `pnpm build` plus the relevant environment or consumer check for TypeScript entrypoints, declarations, ESM/CJS, browser, or bundler behavior. Preserve complete failure output. The full test matrix and focused subsystem map live in [Repository Test Strategy and Safe Validation](/openwiki/testing/repository-test-strategy.md).

## Release authority

Python and TypeScript versioning and publication are independent. The exclusive procedure is `CONTRIBUTING.md` under **Cutting a release**: separate version-bump PRs against `main`, `uv run bump2version` for Python, and `pnpm run bump-version` for TypeScript. Do not hand-edit version files, publish locally, or push release tags. Consult [Development, Generated Code, Builds, and Releases](/openwiki/operations/development-and-release.md) before release work.
