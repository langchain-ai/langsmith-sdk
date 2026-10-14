---
type: repository quickstart
title: LangSmith SDK Repository Quickstart
description: Concise task-oriented entrypoint for engineers changing the Python and JavaScript/TypeScript LangSmith SDK implementations. Routes work to the relevant architecture, concepts, workflows, integrations, testing, and operations guidance.
tags: [quickstart, sdk, python, javascript, typescript, tracing, evaluation, development]
verified:
  - by: openwiki/0.5.2
    at: 2026-10-12T08:42:50.524Z
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
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
generated: { by: "openwiki/0.5.2", at: "2026-10-12T08:42:50.524Z" }
---

# LangSmith SDK Repository Quickstart

This source tree contains two independent `langsmith` implementations for the same observability and evaluation platform: Python under `python/` and JavaScript/TypeScript under `js/`. They share product concepts, not runtime code or an identical API shape. Java and Go SDKs live in their separate repositories.

> **Check the contribution destination before editing.** The presence of both implementations here does not mean this repository is the right destination for new work. Read the current root `CONTRIBUTING.md` and `.github/workflows/ci.yml`: split-repository migration is in progress, the freeze guard can reject changes to moved language folders, and merges from this repository are mirrored to staging repositories with package manifests and lockfiles excluded. At this snapshot `js/` is frozen, but the configured folders and routing can change. Internal and external contributors are directed differently by the guard, so verify current routing, freeze labels, and mirroring exceptions rather than relying on this page.

> **Authority rule:** current source and focused tests are authoritative. These pages are just-in-time orientation, not a substitute for following the implementation and its tests.

## Route the task

Choose the user-visible contract first, then the implementation and repository. Do not mechanically mirror the other language: Python deliberately has distinct synchronous and asynchronous surfaces (`Client`, `AsyncClient`, `evaluate`/`aevaluate`, sync/async caches), while JavaScript exposes promise-based APIs through one principal `Client`.

| If the task is… | Begin at | Detailed page |
|---|---|---|
| Understand layers, handwritten/generated boundaries, imports, packaging, or cross-SDK parity | The language package root and owning implementation | [Dual-SDK Architecture and Public Surfaces](/openwiki/architecture/sdk-architecture.md) |
| Change endpoints, profiles, API keys/OAuth, workspace headers, retries, timeouts, or runtime constraints | The handwritten client constructor and configuration helpers | [Client Configuration, Endpoints, and Authentication](/openwiki/concepts/client-configuration-and-auth.md) |
| Change runs, projects, datasets, examples, feedback, prompts, annotation queues, threads, sharing, or pagination | The public client method or generated-resource accessor | [LangSmith Platform Client Domains](/openwiki/concepts/platform-client.md) |
| Change run identity, nesting, propagation, ordering, streaming completion, attachments, or replica IDs | `RunTree` and tracing-context helpers | [Run Trees, Trace Identity, and Context Propagation](/openwiki/concepts/run-tree-and-context.md) |
| Send a trace to a project or `AgentAddress`, resolve a feature address, or change destination precedence/inheritance | Address and destination types plus their `RunTree`/client integration | [Trace Destinations and Feature Addresses](/openwiki/concepts/trace-destinations-and-addressing.md) |
| Change capture, sampling, privacy transforms, batching, compression, replicas, retries, flush, shutdown, or failed traces | Follow `RunTree` into the client ingestion path | [Trace Capture, Transformation, and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md) |
| Interpret committed ingestion timing, call-count, wire-size, or application-thread measurements | The trace-lab scenarios and their captured conditions | [Measured Trace Ingestion Paths](/openwiki/workflows/trace-ingestion-measured.md) |
| Change evaluation targets, experiments, comparative evaluation, concurrency, repetitions, or evaluator normalization | The language evaluation entrypoint and runner | [Evaluation and Experiment Workflows](/openwiki/workflows/evaluation-and-experiments.md) |
| Add or repair a model, agent, realtime, voice, LangChain, or OpenTelemetry integration | The matching wrapper/integration and focused tests | [Provider Wrappers, Agent Integrations, and OpenTelemetry](/openwiki/integrations/provider-wrappers-and-opentelemetry.md) |
| Change sandbox creation, files, mounts, snapshots, services, commands, tunnels, reconnect, or cleanup | The sandbox client/handle and transport boundary | [Sandbox Lifecycle and Execution Transports](/openwiki/workflows/sandbox-lifecycle-and-execution.md) |
| Choose validation, debug CI, or test export/runtime compatibility | The narrowest test proving the changed contract | [Repository Test Strategy and Safe Validation](/openwiki/testing/repository-test-strategy.md) |
| Build, add an entrypoint, update generated APIs, understand mirroring/freeze controls, benchmark, or release | Repository scripts and protected workflows | [Development, Generated Code, Builds, Mirroring, and Releases](/openwiki/operations/development-and-release.md) |

## Public entrypoints

### Python

`python/langsmith/__init__.py` is a curated lazy facade. Its `__getattr__` resolves public clients, tracing, addresses, evaluation, testing, cache, UUID, secret, and exception APIs on demand, and `__all__` records the supported root-level names. Follow the lazy import to the owning module before changing behavior.

Python exposes separate `Client` and `AsyncClient` types and explicit sync/async API pairs. They are not guaranteed to be complete mirrors; inspect the actual owner and tests for the surface being changed. Packaging is configured in `python/pyproject.toml` with Hatchling and Python 3.10+.

### JavaScript / TypeScript

`js/src/index.ts` is the compact package root: it exports the principal `Client`, selected schemas, `RunTree`, feature-address types, utilities, cache APIs, generated error classes, and version metadata. Tracing, evaluation, Jest/Vitest support, wrappers, OpenTelemetry, and sandbox APIs also use public package subpaths.

`js/scripts/create-entrypoints.js` is the subpath registry and generator. It creates ESM, CommonJS, and declaration shims and synchronizes `package.json` exports/files. Change the registry and rebuild rather than maintaining one module format by hand. JavaScript client operations are promise-based; do not introduce a Python-style second async client merely for naming parity.

## Generated OpenAPI boundary

> **DO NOT EDIT GENERATED CLIENTS BY HAND**
>
> - `python/langsmith/_openapi_client/`
> - `js/src/_openapi_client/`
>
> Stainless generates both trees from the LangSmith OpenAPI contract. Only the authorized external synchronization workflow may update them, and `protect-openapi-client.yml` blocks ordinary pull requests that touch either tree. Endpoint-schema changes belong in the upstream OpenAPI/Stainless process, not in a local patch that will be overwritten.

The handwritten clients are the composition boundary around generated resources. They adapt base URLs, authentication/workspace values, caller and SDK headers, timeouts/transports, and backend-version checks while retaining higher-level compatibility and tracing behavior. When exposing or changing a generated resource, validate both this adapter and the generated call—not just one side.

Generated build output is separate from generated OpenAPI source. TypeScript `dist/` and entrypoint shims are recreated by build scripts; Python tooling suppressing generated-client diagnostics is an ownership signal, not permission to patch generated code.

## Safe change loop

Work from the selected SDK directory. Start with the smallest offline test that demonstrates the contract:

```bash
cd python
TEST=tests/unit_tests/test_client.py make tests
```

```bash
cd js
NODE_OPTIONS=--experimental-vm-modules npx jest src/tests/context.test.ts
```

Then run the required baseline for each implementation touched:

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

Escalate according to the boundary: use credentialed integration tests only for deployed API/provider behavior, `make test-wheel-imports` for Python wheel dependencies, and `pnpm build` plus the relevant environment/export tests for TypeScript declarations, ESM/CommonJS, browser, or bundler changes. Preserve complete failure output and do not weaken network isolation to make an offline test pass.

## Before opening or releasing a change

1. Recheck contribution routing and the current `FROZEN` value in `.github/workflows/ci.yml`.
2. Confirm whether manifest or lockfile edits require a manual port because staging mirroring excludes them.
3. Keep generated OpenAPI directories out of ordinary changes.
4. Run focused tests, then the touched SDK's required baseline and boundary-specific checks.
5. For an external contributor PR, follow the maintainer takeover process; do not authorize its workflows directly.

Python and JavaScript releases are independent. The exclusive procedure is **Cutting a release** in `CONTRIBUTING.md`: separate version-bump PRs against `main`, `uv run bump2version` for Python, and `pnpm run bump-version` for JavaScript. Do not hand-edit version files, publish locally, or push release tags. See [Development, Generated Code, Builds, Mirroring, and Releases](/openwiki/operations/development-and-release.md) for the operational details.
