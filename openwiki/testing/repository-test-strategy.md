---
type: testing strategy
title: Repository Test Strategy and Safe Validation
description: A maintainer guide to choosing the narrowest meaningful Python or TypeScript checks, preserving offline isolation, and escalating through integration, export, compatibility, and performance suites.
tags: [testing, validation, python, typescript, continuous-integration]
verified:
  - by: openwiki/0.5.2
    at: 2026-10-12T08:42:50.524Z
sources:
  - id: openwiki-source-da2782db3eab7ffafd3e6ffb
    resource: repo://.github/actions/js-integration-tests/action.yml
  - id: openwiki-source-a93e3bfc9711dec876b53fb1
    resource: repo://.github/actions/js-vitest-eval-test/action.yml
  - id: openwiki-source-e4356c6252bf553f8703f4b3
    resource: repo://.github/actions/python-integration-tests/action.yml
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-fcfa45d3cc652ec605c0952f
    resource: repo://.github/workflows/codspeed.yml
  - id: openwiki-source-b2d60e3aedc0d5c768840e9a
    resource: repo://.github/workflows/protect-openapi-client.yml
  - id: openwiki-source-aa61974e278ddb346c2c5ac3
    resource: repo://.github/workflows/py-bench-datadog.yml
  - id: openwiki-source-551926675e59cc7f77474cd3
    resource: repo://.github/workflows/py-bench.yml
  - id: openwiki-source-1278717ecdbca75bfb2a542f
    resource: repo://js/AGENTS.md
  - id: openwiki-source-2937fffe86eb25f8c32e8423
    resource: repo://js/internal/environment_tests/docker-compose.yml
  - id: openwiki-source-c855bbd59c32472dea474136
    resource: repo://js/internal/environment_tests/test-deepagent-compat/package.json
  - id: openwiki-source-a0a4ec0871e61d8c1da573f9
    resource: repo://js/internal/environment_tests/test-exports-esm/package.json
  - id: openwiki-source-1962d0d1a656e42c2e3f453e
    resource: repo://js/jest.config.cjs
  - id: openwiki-source-e3bc66e65fbfbbea4eb3b049
    resource: repo://js/package.json
  - id: openwiki-source-6f03acb1dbd0338d2d029c28
    resource: repo://js/src/tests/perf.int.test.ts
  - id: openwiki-source-d43c29b04963c6b47e63055a
    resource: repo://js/src/tests/utils/markers.ts
  - id: openwiki-source-53ab77c903b51559b444a7a4
    resource: repo://js/vitest.config.ts
  - id: openwiki-source-9d11c849d0c541bb26055d77
    resource: repo://python/AGENTS.md
  - id: openwiki-source-1dac2be7544adf0d61a9e562
    resource: repo://python/bench/test_bench.py
  - id: openwiki-source-c1078b3c786277fee3aedc41
    resource: repo://python/conftest.py
  - id: openwiki-source-7ba913c7138ece9a31242d0f
    resource: repo://python/Makefile
  - id: openwiki-source-86f79b074f4ac8d604a1778a
    resource: repo://python/tests/integration_tests/conftest.py
generated: { by: "openwiki/0.5.2", at: "2026-10-12T08:42:50.524Z" }
---

# Repository Test Strategy and Safe Validation

Validate the behavior that changed first, without hiding later failures, and only then widen the test surface. A focused test is the fastest diagnostic loop; it is not a substitute for the full pre-PR commands at the end of this page.

```mermaid
flowchart TD
    A["Identify the changed contract"] --> B["Run one focused offline test"]
    B --> C{"Crosses a live service boundary"}
    C -->|No| D["Run the owning unit suite"]
    C -->|Yes| E["Run a focused credentialed integration test"]
    D --> F{"Changes packaging or runtime assumptions"}
    E --> F
    F -->|Yes| G["Build and run the relevant compatibility check"]
    F -->|No| H["Run required pre-PR commands"]
    G --> H
    H --> I{"Performance-sensitive path"}
    I -->|Yes| J["Compare benchmarks with a stable baseline"]
    I -->|No| K["Review complete failure output"]
    J --> K
```

*The validation ladder begins with an isolated behavioral contract and escalates only at live-service, packaging, runtime, and performance boundaries.*

## Choose the narrowest meaningful check

A test is meaningful when it exercises the changed contract, not merely the edited file. During ordinary local validation, keep all selected failures visible: do not add `-x`, `--maxfail=1`, or `--bail`. Temporarily stopping early can shorten an interactive debugging loop, but rerun the selection without fail-fast before treating it as validated.

### Python

Run from `python/` so the Makefile supplies the repository's `uv` environment and test safeguards.

```bash
# One file, with full names and output
TEST="tests/unit_tests/test_client.py -vv" make tests

# One test node
TEST="tests/unit_tests/test_run_helpers.py::test_name -vv" make tests

# One offline subsystem
TEST="tests/unit_tests/sandbox -vv" make tests
```

`make tests` defaults to `tests/unit_tests`, unsets tracing/API configuration that could leak in from the shell, enables Python and asyncio debug modes, uses the HTTPX compatibility alias, disables network sockets while permitting Unix sockets, and runs pytest workers automatically. Prefer `TEST=... make tests` over a bare `pytest` command because a bare command silently drops those invariants.

A live integration test is a deliberate escalation. Supply the appropriate LangSmith endpoint/key and any provider key the test needs, then clear the Makefile's default `-x` so the selected set reports every failure:

```bash
INT_TEST="tests/integration_tests/test_runs.py" PYTEST_EXIT_FIRST= make integration_tests
PYTEST_EXIT_FIRST= make evals
```

Use `make integration_tests_fast` only when parallel execution is safe for the selected remote resources. Integration tests create, poll, and clean up remote state and can be sensitive to eventual consistency; unit tests should remain the default for request construction, retry policy, serialization, batching, and error mapping.

Slow pytest cases are skipped unless `--runslow` is present. Pass it through `TEST` for unit tests, or through the relevant integration invocation, only when the change requires those cases.

### TypeScript

Run from `js/`. Jest is the main unit/integration runner; Vitest has a separate filename convention and configuration.

```bash
# One Jest unit file
NODE_OPTIONS=--experimental-vm-modules npx jest src/tests/context.test.ts --runInBand

# One integration file; omit --bail so every selected case reports
pnpm test:integration src/tests/client.int.test.ts

# One Vitest-specific file
pnpm test:vitest src/tests/guard.vitesttest.ts
```

The normal `pnpm test` script excludes `*.int.test.ts`; `pnpm test:integration` selects that suffix. Jest runs TypeScript as ESM in a Node environment and ignores Vitest-specific files. Vitest selects `*.vitesttest.*` files. Choose the runner from the test filename rather than assuming the two suites are interchangeable.

## What each suite proves

| Suite | Boundary and intended evidence | Typical failure meaning |
|---|---|---|
| Python/JS unit | Local behavior with mocks, fake transports, or disabled sockets | Logic, serialization, concurrency, retry, or error-contract regression |
| Python/JS integration | A credentialed SDK talks to a deployed LangSmith environment and, for wrapper cases, possibly a model provider | API contract, authentication, backend capability, ingestion visibility, or provider compatibility failure |
| Evaluation | Experiment/evaluator orchestration and test-framework reporting | Result association, evaluator execution, attachment handling, or reporter lifecycle regression |
| JS environment/export | The built local package installs and resolves in a real consumer toolchain | Missing entry point, wrong ESM/CJS declaration, browser/edge-incompatible dependency, or bundler failure |
| External compatibility | The local SDK can coexist with a downstream package such as `deepagents` | Dependency range, import, or package-resolution regression |
| Performance | A stable workload records latency, allocations, or throughput rather than asserting only functional output | Serialization, batching, or event-loop regression; investigate variance before treating one run as conclusive |

CI tests Python unit behavior on Python 3.10–3.13. JavaScript unit jobs use Node 22 and 24 on Linux and Node 24 on Windows and macOS; each builds, checks the package version, then runs Jest and Vitest. A separate Node 24 build job checks the package build/type surface. A local focused pass therefore does not establish supported-version or operating-system compatibility.

The strict Python wheel job is another boundary: `make test-wheel-imports` builds without local source substitutions, installs the wheel with `--no-deps` into a fresh environment, installs exactly the declared runtime dependencies, and imports/constructs representative generated OpenAPI and core clients. Use it whenever dependency declarations, packaging, generated clients, or the HTTPX alias change.

### Environment-aware integration

The backend allowlist contains `beta`, `v16-ch-only`, `v16-dual`, and `v16-smithdb-only`. Push and ordinary pull-request runs use beta; scheduled nightly runs use every environment; a manual dispatch can select one or all. Python runs on 3.11 and creates six deterministic integration shards per environment, one evaluation leg per environment, and one beta-only doctest leg. JavaScript runs unsharded integration and Vitest-evaluation legs on Node 24 for each selected environment.

Python shard ownership is stable because pytest node IDs are hashed modulo six. Backend capability markers remove tests unsupported by a target: ClickHouse-only excludes `require_v2`, SmithDB-only excludes `require_clickhouse`, and non-beta JS targets also exclude `require_beta_dataset`. Do not “fix” an environment-specific failure by globally skipping a test; attach the narrow capability marker only when the endpoint truly is absent there.

Fail-fast exists at two distinct levels:

- Both Python and JavaScript matrix strategies set `fail-fast: false`, so one failed matrix leg does not cancel the other environments or shards.
- Inside each leg, Python push/PR runs normally pass `-x`; nightly clears it, and manual dispatch can choose. JS integration and Vitest evaluation normally omit bail, while a manual dispatch can request it.

Consequently, local debugging choices should not be inferred from CI defaults. Prefer a narrow local selection with fail-fast disabled so it yields complete failure context. CI deliberately retains Python `-x` on routine remote shards to control cost, while still allowing every matrix leg to finish.

The Bun job is separate from the Node integration matrix: it installs with the latest Bun and runs the focused `src/tests/bun/traceable.test.bun.ts` against beta with tracing enabled. It has no SDK path condition and is included in the final CI gate, so it runs even when Python/JS path-filtered jobs are skipped.

## Network isolation, fixtures, and cassettes

Offline tests must fail if production code unexpectedly opens a network socket. Python's `make tests` enforces this with `--disable-socket --allow-unix-socket`; use a fake transport or mock server rather than relaxing the suite globally.

The root Python `conftest.py` installs an automatic VCR fixture. It records/replays only OpenAI and Anthropic traffic, filters authentication-related headers and likely secrets in bodies, and names cassettes from the module and test function. Integration configuration extends this to Gemini. The default `--vcr-mode=once` replays an existing cassette and allows an initial recording; `none` is the strict replay-only choice. Cassette matching normally includes the request body, while doctests and selected provider adapters use more tolerant matching for unstable payload shapes.

Treat cassettes as reviewable fixtures, not opaque snapshots:

- never commit credentials, bearer tokens, signed URLs, or unrelated service traffic;
- re-record only the smallest affected test and inspect the YAML diff;
- keep deterministic request fields stable so replay mismatches reveal contract changes;
- do not use a cassette to replace a LangSmith integration test—the VCR filters intentionally omit non-provider requests.

In JS tests, inject `fetchImplementation`, use the existing mock clients/MSW patterns, or stand up an explicit local fake. Integration polling helpers tolerate eventual consistency and throw a timeout with context; they should not be copied into unit tests to mask nondeterminism.

## Focused change map

Start with the listed seam, then add adjacent tests when a change spans contracts.

| Changed area | Python focus | TypeScript focus | Escalate when |
|---|---|---|---|
| Trace creation, context, batching, ingestion | `tests/unit_tests/test_run_helpers.py`, `test_run_trees.py`, `test_background_thread.py`, `test_hybrid_tracing.py` | `src/tests/traceable.test.ts`, `run_trees.test.ts`, `context.test.ts`, `batch_client.test.ts`, `failed_traces.test.ts` | Run `test_runs.py`, `run_trees.int.test.ts`, `traces.int.test.ts`, or context integration after changing remote visibility or propagation |
| Core client, retries, headers, replicas, attachments | `test_client.py`, `test_async_client.py`, `test_custom_headers.py`, multipart/replica tests | `client.test.ts`, `client_retry.test.ts`, `client_headers.test.ts`, `replica_endpoints.test.ts` | Use client integration tests for endpoint and backend behavior; use wheel/export tests for dependency/import changes |
| Evaluation and test-framework adapters | `tests/unit_tests/evaluation/`, then `tests/evaluation/` | `evaluate_runner.test.ts`, `src/tests/jestlike/`, `vitest_reporter.vitesttest.ts` | Run Python `make evals` or `pnpm test:eval:vitest` when result upload/reporting crosses LangSmith |
| Provider and agent wrappers | `tests/unit_tests/wrappers/` | the matching `wrapped_*.test.ts`, agent SDK, or Vercel test | Run the matching wrapper integration file when provider request/response translation changes; use sanitized cassettes where supported |
| Sandbox lifecycle, command transport, WebSocket/Yamux | `tests/unit_tests/sandbox/`, especially command retry, transport, tunnel, and sync/async conversion | `sandbox.test.ts` plus handshake, reconnect acknowledgment, command-ID retry, and error tests | Use live sandbox validation only for server-owned lifecycle or protocol behavior; see [Sandbox Lifecycle and Execution](/openwiki/workflows/sandbox-lifecycle-and-execution.md) |
| Public exports, generated entry points, runtime compatibility | Build first, then `make test-wheel-imports` for Python runtime dependencies | Build first, then the one `js/internal/environment_tests` Docker service matching ESM, CJS, Cloudflare, Vite, Webpack, esbuild, or Metro | Run all environment jobs when changing `package.json` exports, entrypoint generation, declarations, or shared runtime dependencies |
| Performance-sensitive tracing/serialization | Start with `make benchmark-fast`, then use the instrumented suites described below | opt in to `src/tests/perf.int.test.ts` with `LANGSMITH_RUN_PERF_BENCH=true` | Compare against a baseline on the same machine/CI; the JS benchmark uses a fake fetch and emits machine-readable results |

For a JS export check, build the package before starting the isolated consumer:

```bash
cd js
pnpm build
cd ..
docker compose -f js/internal/environment_tests/docker-compose.yml run test-exports-esm
```

Replace the service with `test-exports-cjs`, `test-exports-cf`, `test-exports-vite`, `test-exports-webpack`, `test-exports-esbuild`, or `test-exports-metro` as appropriate. Each Node 22 container installs `langsmith` from the mounted repository and exercises a real consumer compilation/bundling path. The Compose file also provides `test-deepagent-compat`; CI runs it separately as a downstream compatibility check.

Generated OpenAPI client directories are a special ownership boundary: do not hand-edit `python/langsmith/_openapi_client/` or `js/src/_openapi_client/`. Pull requests touching them are accepted only from the authorized SDK synchronization workflow. Validate changes at the generator/sync source rather than trying to bypass the protection check.

## Performance-test ladder

The Python benchmark entrypoints share the workloads in `bench.cases`, but answer different questions:

1. **Fast local/PR comparison:** `make benchmark-fast` runs the pyperf harness in fast mode and writes `out/benchmark.json`. The `py-bench` PR workflow is gated only by changes under `python/langsmith/**`; it requires a cached `out/benchmark-baseline.json`, renames baseline and change outputs, and publishes a `pyperf compare_to --table --group-by-speed` annotation. A missing baseline is an intentional failure, not permission to compare unrelated machines.
2. **CodSpeed instrumentation:** `make benchmark-codspeed` exposes the same cases through pytest-benchmark. CodSpeed runs Python 3.13 on stable macro runners as independent `memory` and `walltime` matrix legs with matrix fail-fast disabled. Memory tracks heap allocation and walltime captures real elapsed time, including tracing-thread work. The simulation leg is currently disabled because Valgrind is too slow on the ARM64 runner. CI disables pytest's normal timeout for these instrumented runs.
3. **Datadog historical reporting:** `make benchmark-datadog` uses plain pytest-benchmark. PRs from the same repository execute the benchmark but deliberately skip Datadog configuration, so PR-controlled code never receives `DD_API_KEY` and does not upload. Fork PRs skip the job entirely. Main-branch and manual runs configure Datadog immediately before the benchmark and report the Python 3.13 results to the `langsmith-sdk-python` service on the `us5.datadoghq.com` site.

CodSpeed and Datadog workflows watch implementation, benchmark, dependency/lockfile, Makefile, and their own workflow configuration so baseline/reporting changes are exercised with the code that caused them. Use fast pyperf for quick directional comparison, CodSpeed for allocation and walltime instrumentation, and Datadog for trusted main-branch history; they are complementary rather than interchangeable gates.

## CI selection and repository guards

The broad `changes` job opts Python jobs into changes under `python/**` or `.github/**`, and JS jobs into `js/**` or `.github/**`; scheduled runs opt both in. Integration selection is narrower on pull requests: it detects changed `python/**/*.py` and JS source extensions, while the `release` label forces both relevant integration suites. Pushes run both integration suites against beta, schedules run all environments, and dispatch inputs control whether each language runs.

Pull requests also pass through the freeze guard. The current `FROZEN` list contains `js`, so a PR touching or renaming a path under `js/` fails with migration guidance. Maintainers may apply `skip-freeze-guard` only for a revert or hotfix that must ship from this repository; the skipped result is accepted by the aggregate gate.

`CI Success` always evaluates all declared dependencies, including lint/unit, wheel, export, compatibility, integration, Vitest evaluation, Bun, change detection, and freeze guard. It fails if any dependency result is `failure` or `cancelled`, but accepts `success` and legitimate `skipped` results. This is why path-gated jobs and the label-bypassed freeze guard can still produce a successful required check.

## Required full pre-PR validation

After focused tests pass, run the complete commands required for every SDK you changed. Do not replace them with the narrower examples above.

From `python/`:

```bash
make format
make lint
make tests
```

From `js/`:

```bash
pnpm format
pnpm lint
pnpm test
```

For TypeScript changes that affect types, packaging, Vitest adapters, or exports, also run the corresponding `pnpm build`, `pnpm test:vitest`, and environment test even though the three commands above are the repository's pre-PR baseline. For integration-boundary changes, run the focused live suite with credentials and no fail-fast, then use CI's backend matrix for environment coverage.

Related operational context is in [Development and Release](/openwiki/operations/development-and-release.md); assertion/reporting behavior is covered by [Test Tracking and Assertions](/openwiki/testing/test-tracking-and-assertions.md), and tracing integration behavior by [Trace Capture and Ingestion](/openwiki/workflows/trace-capture-and-ingestion.md).
