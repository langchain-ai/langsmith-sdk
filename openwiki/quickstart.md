---
type: repository quickstart
title: LangSmith SDK Repository Quickstart
description: Task-oriented map for the Python and JavaScript/TypeScript SDKs implemented in this repository, with external pointers to the supported Java and Go SDKs. Routes agents to architecture, tracing, platform concepts, workflows, tests, integrations, and operations.
tags: [quickstart, sdk, python, javascript, typescript, java, go, tracing, evaluation, development]
verified:
  - by: openwiki/0.5.2
    at: 2026-09-16T06:53:56.756Z
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
generated: { by: "openwiki/0.5.2", at: "2026-09-16T06:53:56.756Z" }
---

# LangSmith SDK Repository Quickstart

This repository owns two independently implemented `langsmith` packages for the same LangSmith observability and evaluation platform: Python under `python/` and JavaScript/TypeScript under `js/`. They cover parallel product concepts, but they are not bindings over shared runtime code and do not guarantee identical API shape. Before making a “cross-SDK” change, verify the behavior, naming, lifecycle, and tests in both languages.

> **Supported SDK ecosystem**
>
> - **Python:** implemented here in [`python/`](../python/).
> - **JavaScript/TypeScript:** implemented here in [`js/`](../js/).
> - **Java:** maintained externally at [langchain-ai/langsmith-java](https://github.com/langchain-ai/langsmith-java); Java source is not in this repository.
> - **Go:** maintained externally at [langchain-ai/langsmith-go](https://github.com/langchain-ai/langsmith-go); Go source is not in this repository.
>
> Scope changes, implementation work, and local validation accordingly: this repository owns only the Python and JavaScript/TypeScript implementations.

> **Authority rule:** source code and tests are authoritative. The generated OpenWiki pages linked below are optional, just-in-time context—not required startup reading and not a substitute for checking the current implementation and focused tests.

## Start with the contract you are changing

Choose the user-visible task first, then select the language implementation. Do not begin by mechanically mirroring a file from the other SDK: Python has distinct synchronous and asynchronous clients, while JavaScript uses promise-based methods on one principal `Client`; runtime types, packaging, and integration support also differ.

| If the task is… | Start here | Then read |
|---|---|---|
| Understand SDK layers, public imports, sync/async differences, or parity | Python `langsmith/__init__.py`; TypeScript package root and subpath exports | [Dual-SDK Architecture and Public Surfaces](/openwiki/architecture/sdk-architecture.md) |
| Change endpoint, API key, workspace, profile, headers, retries, or browser behavior | The relevant handwritten client constructor and configuration helpers | [Client Configuration, Endpoints, and Authentication](/openwiki/concepts/client-configuration-and-auth.md) |
| Add or change runs, projects, datasets, examples, feedback, prompts, queues, threads, or sharing | The public handwritten client and its generated-resource bridge | [LangSmith Platform Client Domains](/openwiki/concepts/platform-client.md) |
| Change run identity, parent/child nesting, propagation, streaming completion, tags, or metadata | `RunTree` and tracing-context helpers | [Run Trees, Trace Identity, and Context Propagation](/openwiki/concepts/run-tree-and-context.md) |
| Change sampling, privacy transforms, batching, compression, replicas, retries, flush, or dropped traces | Follow capture through `RunTree` into the client ingestion path | [Trace Capture, Transformation, and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md) |
| Investigate ingestion-path timing, HTTP-call count, wire size, or application-thread occupancy | Compare the trace lab's durable direct, batched, multipart, compressed, OTEL, and hybrid capture | [Measured Trace Ingestion Paths](/openwiki/workflows/trace-ingestion-measured.md) |
| Change dataset evaluation, experiment execution, concurrency, repetitions, or evaluators | The language's evaluation entrypoint and runner | [Evaluation and Experiment Workflows](/openwiki/workflows/evaluation-and-experiments.md) |
| Change pytest, Jest, or Vitest tracking and assertions | The test-framework adapter plus reporter/plugin lifecycle | [LangSmith Test Tracking and Evaluation Assertions](/openwiki/testing/test-tracking-and-assertions.md) |
| Add or repair a model, agent, realtime, LangChain, or OpenTelemetry integration | The matching wrapper/integration, its provider normalization, and focused tests | [Provider Wrappers, Agent Integrations, and OpenTelemetry](/openwiki/integrations/provider-wrappers-and-opentelemetry.md) |
| Change sandbox creation, files, commands, tunnels, mounts, auth proxies, reconnect, or cleanup | The public sandbox client/handle and transport boundary | [Sandbox Lifecycle, Files, Tunnels, and Command Execution](/openwiki/workflows/sandbox-lifecycle-and-execution.md) |
| Choose tests or diagnose CI/export compatibility | Start with the narrowest test that proves the changed contract | [Repository Test Strategy and Safe Validation](/openwiki/testing/repository-test-strategy.md) |
| Build, add a package entrypoint, update generated APIs, or release | Follow repository-owned scripts and protected workflows | [Development, Generated Code, Builds, and Releases](/openwiki/operations/development-and-release.md) |

## Public entrypoints and ownership

### Python

`python/langsmith/__init__.py` is the curated package facade. It lazily resolves public names through module `__getattr__` and records the supported root surface in `__all__`. Important root-level families include `Client`, `AsyncClient`, `RunTree`, `traceable`, tracing-context helpers, sync/async evaluation functions, testing helpers, prompt caches, and stable SDK exceptions. Follow the lazy import to the owning module before editing behavior.

Use `Client` for the mature synchronous and tracing-oriented surface and `AsyncClient` for asynchronous HTTP and lifecycle use. Do not assume they are exact mirrors. Python is packaged with Hatchling, requires Python 3.10 or later, and exposes a pytest plugin through the `langsmith_plugin` entry point.

### TypeScript / JavaScript

`js/src/index.ts` intentionally exposes a compact root including `Client`, selected schema types, `RunTree`, cache and UUID utilities, generated error classes, and version metadata. Tracing, evaluation, wrappers, sandbox, Jest/Vitest support, and experimental OpenTelemetry APIs are primarily public package subpaths such as `langsmith/traceable`, `langsmith/evaluation`, `langsmith/wrappers`, and `langsmith/sandbox`.

The subpath registry is `js/scripts/create-entrypoints.js`. It generates ESM, CommonJS, and declaration shims and synchronizes `package.json` `exports` and `files`; do not maintain just one module format by hand. A public-surface change is incomplete until the package builds and the relevant consumer/export check passes.

## The generated-code boundary

The directories below are generated from the LangSmith OpenAPI contract through Stainless:

- `python/langsmith/_openapi_client/`
- `js/src/_openapi_client/`

**Never edit either directory manually.** Authorized generated changes arrive through the external SDK synchronization workflow, and repository CI rejects ordinary pull requests that touch these trees. Put tracing policy, compatibility, configuration adaptation, orchestration, and higher-level behavior in handwritten code outside them. If the endpoint/resource contract itself must change, use the upstream OpenAPI/Stainless process.

The handwritten clients remain the composition boundary: they own established configuration and tracing behavior and expose selected generated resource families. Therefore, when adding a generated resource to a public client, verify the adapter's base URL, API key, workspace headers, timeout, custom transport/header behavior, backend compatibility policy, and public typing—not only the generated method.

Generated build artifacts are a separate concern. In TypeScript, root shims and `dist/` are recreated by build scripts; change the entrypoint registry and rebuild. In Python, lint/type configuration deliberately excludes or suppresses generated-client diagnostics; that is an ownership signal, not permission to patch generated output.

## Safe change loop

Work from the SDK directory and first run a focused, offline test for the behavior you changed. Python's Makefile supplies network isolation and its managed `uv` environment:

```bash
cd python
TEST=tests/unit_tests/test_client.py make tests
```

TypeScript's documented focused Jest invocation is:

```bash
cd js
NODE_OPTIONS=--experimental-vm-modules npx jest src/tests/context.test.ts
```

Then run the complete baseline for every SDK touched:

```bash
# from python/
make format
make lint
make tests
```

```bash
# from js/
pnpm format
pnpm lint
pnpm test
```

Escalate only when the changed boundary requires it: use credentialed integration tests for deployed API/provider behavior, `make test-wheel-imports` for Python packaging/runtime dependencies, and `pnpm build` plus the relevant environment/export suite for TypeScript entrypoints, declarations, ESM/CJS, browser, or bundler behavior. Preserve complete failure output and do not weaken network isolation merely to make an offline test pass.

## Release guardrails

Python and TypeScript versions and publication workflows are independent. The exclusive release procedure is the “Cutting a release” section of `CONTRIBUTING.md`: create separate version-bump PRs against `main`, use `uv run bump2version` for Python or `pnpm run bump-version` for TypeScript, and do not hand-edit version files, publish locally, or push release tags. See [Development, Generated Code, Builds, and Releases](/openwiki/operations/development-and-release.md) before any release-related change.
