# Threat Model: langsmith-sdk

> Generated: 2026-04-07 | Commit: d60d315 | Scope: Python SDK (`python/langsmith/`) and JS/TS SDK (`js/src/`)

> **Disclaimer:** This threat model is automatically generated to help developers and security researchers understand where trust is placed in this system and where boundaries exist. It is experimental, subject to change, and not an authoritative security reference -- findings should be validated before acting on them. The analysis may be incomplete or contain inaccuracies. We welcome suggestions and corrections to improve this document.

## Scope

### In Scope

- `python/langsmith/` -- Python SDK source (client, tracing, evaluation, sandbox, anonymizer, middleware, wrappers, integrations, prompt management)
- `js/src/` -- JavaScript/TypeScript SDK source (client, tracing, evaluation, sandbox, anonymizer, wrappers, experimental modules)
- `openapi/` -- OpenAPI specification (informs API surface understanding)
- Configuration loading from environment variables (`LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, `LANGSMITH_ENDPOINT`, etc.)

### Out of Scope

- LangSmith backend/server (this is a client SDK -- server security is not modeled here)
- User application code that consumes the SDK
- LLM provider APIs (OpenAI, Anthropic, Gemini, etc.) -- the SDK wraps these but does not control them
- Sandbox server infrastructure -- the SDK is a client to the sandbox service
- Deployment infrastructure, CI/CD, container security
- `tests/`, `bench/`, `docs/`, `examples/` -- not shipped code
- Third-party dependencies beyond their API contracts
- `node_modules/` contents

### Assumptions

1. The project is used as a client library -- users control their own application code, model selection, and deployment.
2. The LangSmith API is a trusted, authenticated service. The SDK trusts API responses after authenticating with an API key.
3. API keys are provided by the deployer via environment variables or constructor arguments. The SDK does not generate or rotate keys.
4. The sandbox service is a remote, authenticated service. The SDK trusts sandbox dataplane responses after API key authentication.
5. Network transport uses HTTPS by default (`https://api.smith.langchain.com`). Users who override the endpoint to use HTTP accept the associated risk.

---

## System Overview

The LangSmith SDK provides Python and JavaScript/TypeScript client libraries for interacting with the LangSmith observability and evaluation platform. The SDK captures trace data (inputs, outputs, metadata) from LLM applications, uploads it to the LangSmith API, and provides evaluation, prompt management, and sandbox execution capabilities. It integrates with LangChain, OpenAI, Anthropic, Gemini, and other LLM frameworks.

### Architecture Diagram

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                      User Application                            │
 │  (LangChain, OpenAI, Anthropic, Gemini, custom code)            │
 │                                                                  │
 │  @traceable / wrappers / RunTree / evaluate()                    │
 └───────────┬──────────────────────────┬───────────────────────────┘
             │                          │
             │ Trace data (DF1)         │ Prompt pull (DF3)
             │ Eval data (DF2)          │ Sandbox ops (DF5)
             ▼                          ▼
 ┌──────────────────────┐   ┌──────────────────────┐
 │   LangSmith API      │   │   Sandbox Dataplane  │
 │  (api.smith.lang-    │   │   (per-sandbox URL)  │
 │   chain.com)         │   │   HTTP + WebSocket   │
 └──────────────────────┘   └──────────────────────┘
             │
             │ Distributed tracing (DF4)
             │ (langsmith-trace header)
             ▼
 ┌──────────────────────┐
 │  Downstream Service  │
 │  (optional, user-    │
 │   deployed)          │
 └──────────────────────┘
```

---

## Components

| ID | Component | Description | Trust Level | Default? | Entry Points |
|----|-----------|-------------|-------------|----------|--------------|
| C1 | Python Client | Main API client for LangSmith platform. Creates/reads/updates runs, datasets, feedback, prompts. | framework-controlled | Yes | `client.py:Client.__init__`, `client.py:Client.create_run`, `client.py:Client.pull_prompt` |
| C2 | JS/TS Client | JavaScript equivalent of the Python client. | framework-controlled | Yes | `client.ts:Client` constructor, `client.ts:Client.createRun` |
| C3 | Tracing System | Captures function call traces via `@traceable` decorator (Python) and `traceable()` wrapper (JS). Manages RunTree lifecycle. | framework-controlled | Yes | `run_helpers.py:traceable`, `run_trees.py:RunTree`, `traceable.ts:traceable` |
| C4 | Evaluation Framework | Runs evaluations against datasets, supports LLM-as-judge and custom evaluators. | framework-controlled | No (explicit opt-in required) | `evaluation/_runner.py:evaluate`, `evaluation/index.ts` |
| C5 | Sandbox Client | Manages remote sandboxes for code execution. HTTP + WebSocket communication with sandbox dataplanes. | framework-controlled | No (separate install: `pip install langsmith[sandbox]`) | `sandbox/_client.py:SandboxClient`, `sandbox/_sandbox.py:Sandbox.run` |
| C6 | Anonymizer | Data masking for trace inputs/outputs using regex rules or callable processors. | framework-controlled | No (explicit opt-in required) | `anonymizer.py:create_anonymizer`, `anonymizer/index.ts` |
| C7 | Distributed Tracing Middleware | ASGI middleware that extracts `langsmith-trace` headers and propagates tracing context. | framework-controlled | No (explicit opt-in required) | `middleware.py:TracingMiddleware.__call__` |
| C8 | LLM Provider Wrappers | Wraps OpenAI, Anthropic, Gemini SDKs to auto-trace LLM calls. | framework-controlled | No (explicit opt-in required) | `wrappers/_openai.py`, `wrappers/_anthropic.py`, `wrappers/_gemini.py` |
| C9 | Prompt Management | Pull/push prompts from/to LangSmith. Pull path deserializes manifests via `langchain_core.load.load()`. | framework-controlled | No (explicit opt-in required) | `client.py:Client.pull_prompt`, `client.py:Client.push_prompt` |
| C10 | OTEL Integration | OpenTelemetry span exporter that translates LangSmith traces to OTLP format. | framework-controlled | No (separate install: `pip install langsmith[otel]`) | `integrations/otel/processor.py`, `experimental/otel/exporter.ts` |
| C11 | Agent SDK Integrations | Integrations for Claude Agent SDK, OpenAI Agents SDK, Google ADK. Wraps agent lifecycle with tracing. | framework-controlled | No (separate install per integration) | `integrations/claude_agent_sdk/`, `integrations/openai_agents_sdk/`, `integrations/google_adk/` |
| C12 | Background Tracing Thread | Batches and compresses trace data, sends to LangSmith API via multipart HTTP in a background thread. | framework-controlled | Yes | `_internal/_background_thread.py:tracing_control_thread_func` |
| C13 | Serialization Layer | JSON serialization with orjson, handles Pydantic models, datetimes, UUIDs. Falls back to stdlib json. | framework-controlled | Yes | `_internal/_serde.py:dumps_json`, `_internal/_orjson.py` |

---

## Data Classification

| ID | PII Category | Specific Fields | Sensitivity | Storage Location(s) | Encrypted at Rest | Retention | Regulatory |
|----|-------------|----------------|-------------|---------------------|-------------------|-----------|------------|
| DC1 | API Credentials | `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Critical | Environment variables, process memory | N/A (in-memory only) | Process lifetime | All |
| DC2 | LLM Trace Inputs/Outputs | Function arguments, LLM responses, tool call results captured by `@traceable` and wrappers | High | Transmitted to LangSmith API; optionally written to fallback directory on send failure | In transit: Yes (HTTPS) | Controlled by LangSmith server retention | GDPR, CCPA (if inputs contain PII) |
| DC3 | Evaluation Data | Dataset examples (inputs, expected outputs, reference outputs), evaluation scores | Medium | Transmitted to LangSmith API | In transit: Yes (HTTPS) | Controlled by LangSmith server | GDPR (if examples contain PII) |
| DC4 | Prompt Manifests | Serialized LangChain objects, may contain secret references (`{"type": "secret"}`) | Medium | Fetched from LangSmith API, held in memory/cache | In transit: Yes (HTTPS) | Cache TTL or process lifetime | -- |
| DC5 | Distributed Tracing Headers | `langsmith-trace`, `baggage` headers containing trace IDs, metadata, tags, project names | Low | HTTP headers between services | In transit: depends on user's deployment | Request lifetime | -- |
| DC6 | Sandbox Command I/O | Commands sent to sandboxes, stdout/stderr returned, file content read/written | High | Transmitted to sandbox dataplane via HTTP/WebSocket | In transit: Yes (HTTPS/WSS) | Sandbox lifetime | -- |

### Data Classification Details

#### DC1: API Credentials

- **Fields**: `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGSMITH_RUNS_ENDPOINTS` (may contain API keys in JSON)
- **Storage**: Environment variables read at `utils.py:get_env_var`, cached via `@functools.lru_cache`. Held in `Client._api_key` (Python) and `Client.apiKey` (JS) as instance attributes.
- **Access**: Any code with access to the `Client` instance or `os.environ`.
- **Encryption**: Not encrypted in memory. Transmitted in `x-api-key` HTTP header over HTTPS.
- **Retention**: Process lifetime. The `lru_cache` on `get_env_var` means values persist until process exit.
- **Logging exposure**: The SDK does not log API keys directly. However, trace data captured by `@traceable` could inadvertently capture API keys if they appear in function arguments. The anonymizer (C6) can mitigate this if configured.
- **Gaps**: `LANGSMITH_RUNS_ENDPOINTS` env var contains API keys in JSON (`[{"api_url": "...", "api_key": "..."}]`) at `run_trees.py:_parse_write_replicas_from_env_var`. These are parsed and stored as `WriteReplica` dicts.

#### DC2: LLM Trace Inputs/Outputs

- **Fields**: Arbitrary user data -- function arguments (`inputs`), return values (`outputs`), error messages (`error`), metadata, tags
- **Storage**: Serialized via `_internal/_serde.py:dumps_json`, batched in `_internal/_background_thread.py`, compressed with zstandard, sent to LangSmith API via multipart POST. On send failure, may be written to `_failed_traces_dir` (`client.py:Client._failed_traces_dir`).
- **Access**: Background tracing thread, LangSmith API.
- **Encryption**: In transit via HTTPS. Fallback files on disk are not encrypted.
- **Retention**: In memory until batch flush (~100ms or size threshold). Fallback files: up to `_failed_traces_max_bytes` on disk.
- **Logging exposure**: Trace data may contain PII, credentials, or sensitive business data depending on the user's application. The `hide_inputs`, `hide_outputs`, `hide_metadata` callbacks and the `anonymizer` parameter on `Client.__init__` provide opt-in redaction.
- **Gaps**: Fallback trace files written to disk are not encrypted. Default `_failed_traces_dir` is `~/.langsmith/.runs/` (if writable) with a 100MB cap.

---

## Trust Boundaries

| ID | Boundary | Description | Controls (Inside) | Does NOT Control (Outside) |
|----|----------|-------------|-------------------|---------------------------|
| TB1 | SDK <> LangSmith API | HTTPS boundary between SDK and LangSmith platform | API key authentication, request construction, TLS transport, URL validation | Server-side authorization, data storage, retention policies |
| TB2 | SDK <> User Application | Interface between the SDK and user code | Public API surface, default configurations, input serialization, anonymizer pipeline | What users trace, which functions are decorated, how inputs are structured, model selection |
| TB3 | SDK <> Sandbox Dataplane | HTTP/WebSocket boundary to sandbox execution service | API key authentication (`X-Api-Key` header), URL construction from `dataplane_url` | Sandbox container security, command execution isolation, file system isolation |
| TB4 | Distributed Tracing Header Boundary | `langsmith-trace` and `baggage` headers between services | Header parsing, replica field filtering (`_filter_replica_for_headers`), trace context extraction | Header integrity in transit, upstream service trustworthiness |
| TB5 | SDK <> langchain_core Deserialization | Prompt manifest deserialization via `langchain_core.load.load()` | `allowed_objects` parameter (`"core"` by default), `secrets_from_env=False` default | What objects `langchain_core` allows within its allowlist, manifest content from LangSmith API |

### Boundary Details

#### TB1: SDK <> LangSmith API

- **Inside**: SDK constructs HTTP requests with `x-api-key` header (`client.py:Client.__init__`). Uses `requests` (Python) and `fetch` (JS) for transport. Default endpoint is `https://api.smith.langchain.com` (`utils.py:get_api_url`). API key is loaded from `LANGSMITH_API_KEY` or `LANGCHAIN_API_KEY` environment variables (`utils.py:get_api_key`).
- **Outside**: Server-side authentication, authorization (workspace membership), data storage, rate limiting.
- **Crossing mechanism**: HTTPS POST/GET with API key in header.

#### TB4: Distributed Tracing Header Boundary

- **Inside**: `run_trees.py:RunTree.from_headers` parses the `langsmith-trace` header to extract parent span information. `run_trees.py:_Baggage.from_header` parses the `baggage` header for metadata, tags, project name, and replicas. The `_filter_replica_for_headers` function strips security-sensitive fields (`api_url`, `api_key`, `auth`) from header-supplied replicas, allowing only `project_name` and `updates`.
- **Outside**: The content of the `langsmith-trace` and `baggage` headers, which may be attacker-controlled in multi-service deployments where upstream services are not fully trusted.
- **Crossing mechanism**: HTTP headers on incoming requests, parsed by `TracingMiddleware` (C7) or direct `RunTree.from_headers` calls.

#### TB5: SDK <> langchain_core Deserialization

- **Inside**: `client.py:_process_prompt_manifest` calls `langchain_core.load.load()` with `allowed_objects="core"` (default) or `"all"` (when `include_model=True`). `secrets_from_env` defaults to `False`, preventing environment variable exfiltration via crafted secret fields. Version check (`client.py:_lc_load_allowed_objects_arg_supported`) verifies langchain_core supports the `allowed_objects` parameter.
- **Outside**: The prompt manifest content fetched from the LangSmith API. In shared workspaces, any member with write access can push a manifest. The `langchain_core.load.load()` implementation and its allowlist of deserializable classes.
- **Crossing mechanism**: Python function call passing a dict (manifest) from API response to `langchain_core.load.load()`.

---

## Data Flows

| ID | Source | Destination | Data Type | Classification | Crosses Boundary | Protocol |
|----|--------|-------------|-----------|----------------|------------------|----------|
| DF1 | User Application (C3, C8, C11) | LangSmith API (via C1/C2, C12) | Trace data (inputs, outputs, metadata, errors) | DC2 | TB1 | HTTPS multipart POST |
| DF2 | User Application (C4) | LangSmith API (via C1/C2) | Evaluation data (examples, scores, feedback) | DC3 | TB1 | HTTPS POST/GET |
| DF3 | LangSmith API | User Application (via C9) | Prompt manifests (serialized LangChain objects) | DC4 | TB1, TB5 | HTTPS GET, then `langchain_core.load.load()` deserialization |
| DF4 | Upstream Service | Downstream Service (via C7) | Tracing context (trace IDs, metadata, tags, replicas) | DC5 | TB4 | HTTP headers (`langsmith-trace`, `baggage`) |
| DF5 | User Application (C5) | Sandbox Dataplane | Shell commands, file content | DC6 | TB3 | HTTPS POST, WebSocket (WSS) |
| DF6 | Sandbox Dataplane | User Application (C5) | Command stdout/stderr, file content, exit codes | DC6 | TB3 | HTTPS response, WebSocket messages |
| DF7 | Environment Variables | SDK Configuration (C1, C2, C5) | API keys, endpoint URLs, feature flags | DC1 | TB2 | `os.environ` / `process.env` reads |
| DF8 | User Application | SDK (C6) | Raw trace data for anonymization | DC2 | TB2 | Python/JS function call |
| DF9 | SDK (C3) | Local Filesystem | Failed trace data (fallback on API errors) | DC2 | -- | File write to `~/.langsmith/.runs/` |
| DF10 | User Application (C5) | Sandbox Dataplane (via Tunnel) | Arbitrary TCP traffic tunneled through WebSocket | DC6 | TB3 | TCP over yamux over WebSocket |

### Flow Details

#### DF3: LangSmith API -> User Application (Prompt Pull)

- **Data**: Prompt manifests containing serialized LangChain objects. May include `{"type": "secret"}` nodes referencing API keys.
- **Validation**: `client.py:_process_prompt_manifest` passes `allowed_objects="core"` (default) to `langchain_core.load.load()`, restricting deserialization to `langchain_core` types. When `include_model=True`, `allowed_objects="all"` is used, expanding to partner integrations. `secrets_from_env=False` by default prevents environment variable exfiltration.
- **Trust assumption**: The LangSmith API is authenticated. However, in shared workspaces, any member with write access can push malicious prompts. The `allowed_objects` parameter is the primary defense.

#### DF4: Distributed Tracing Header Propagation

- **Data**: `langsmith-trace` header (dotted order trace IDs), `baggage` header (JSON-encoded metadata, tags, project name, replicas).
- **Validation**: `run_trees.py:_filter_replica_for_headers` strips `api_url`, `api_key`, and `auth` from header-supplied replicas. Only `project_name` and `updates` fields are preserved. Legacy tuple format hardcodes `api_url=None`.
- **Trust assumption**: Headers may be attacker-controlled in multi-service deployments. The SDK must not trust header content to redirect trace data to arbitrary endpoints.

#### DF9: Failed Trace Fallback to Disk

- **Data**: Serialized trace data (JSON, potentially containing PII).
- **Validation**: Capped at `_failed_traces_max_bytes` (default 100MB). Written to `~/.langsmith/.runs/` or system temp directory.
- **Trust assumption**: The local filesystem is trusted. No encryption at rest.

---

## Threats

| ID | Data Flow | Classification | Threat | Boundary | Severity | Validation | Code Reference |
|----|-----------|----------------|--------|----------|----------|------------|----------------|
| T1 | DF3 | DC4 | Unsafe deserialization via `pull_prompt()` with outdated `langchain_core` | TB5 | Medium | Likely | `client.py:_process_prompt_manifest`, `client.py:_lc_load_allowed_objects_arg_supported` |
| T2 | DF3 | DC4 | Expanded attack surface when `include_model=True` allows partner integration class instantiation | TB5 | Medium | Verified | `client.py:_process_prompt_manifest` (line 338) |
| T3 | DF4 | DC5 | Data integrity manipulation via `updates` field in header-supplied replicas | TB4 | Low | Verified | `run_trees.py:_Baggage.from_header` (line 1019-1024), `run_trees.py:_remap_for_project` |
| T4 | DF9 | DC2 | Sensitive trace data written unencrypted to disk on API failure | -- | Low | Verified | `client.py:Client._failed_traces_dir` |
| T5 | DF1 | DC2 | Inadvertent PII/credential capture in trace data | TB1 | Info | Unverified | `run_helpers.py:traceable`, `_internal/_serde.py:dumps_json` |

### Threat Details

#### T1: Unsafe deserialization via `pull_prompt()` with outdated langchain_core

- **Flow**: DF3 (LangSmith API -> User Application via prompt pull)
- **Description**: When `langchain_core` version is between 1.0.0 and 1.2.4 (which satisfies the SDK's `langchain-core>=1.0.0` requirement but predates `allowed_objects` support), `_lc_load_allowed_objects_arg_supported()` returns `False` and no `allowed_objects` restriction is passed to `load()`. Older versions of `langchain_core.load.load()` may not have a default allowlist, potentially allowing unrestricted deserialization of manifests pushed by workspace members.
- **Preconditions**: User has `langchain-core` 1.0.0-1.2.4 installed. An attacker has write access to the same LangSmith workspace and pushes a malicious prompt manifest. The user calls `pull_prompt()`.

#### T2: Expanded attack surface with `include_model=True`

- **Flow**: DF3 (LangSmith API -> User Application via prompt pull)
- **Description**: When `include_model=True`, `allowed_objects="all"` is passed to `langchain_core.load.load()`, allowing instantiation of LLM classes from partner packages (e.g., `langchain_openai.ChatOpenAI`, `langchain_anthropic.ChatAnthropic`). These classes may make network calls during `__init__` or have other constructor side effects. While `secrets_from_env=False` prevents API key exfiltration, attacker-controlled constructor kwargs could trigger network requests to attacker-controlled endpoints.
- **Preconditions**: User calls `pull_prompt(include_model=True)`. Attacker has write access to the workspace. Relevant partner packages are installed.

#### T3: Data integrity manipulation via `updates` in header-supplied replicas

- **Flow**: DF4 (Distributed tracing headers)
- **Description**: The `updates` field passes through `_filter_replica_for_headers` (it is in `_HEADER_SAFE_REPLICA_FIELDS`). When applied via `dup.update(updates)`, an attacker who controls the `baggage` header can overwrite arbitrary keys in the run dict (e.g., `session_name`, `inputs`, `outputs`), potentially polluting trace data sent to replica endpoints.
- **Preconditions**: Attacker can send HTTP requests with crafted `baggage` header to a service using `TracingMiddleware` or `RunTree.from_headers`. Tracing replicas are configured.

#### T4: Sensitive trace data written unencrypted to disk

- **Flow**: DF9 (Failed traces to local filesystem)
- **Description**: When the SDK cannot reach the LangSmith API, trace data (which may contain PII, credentials, or sensitive business data) is written unencrypted to `~/.langsmith/.runs/` or a system temp directory, capped at 100MB. On shared systems, other users may be able to read these files.
- **Preconditions**: LangSmith API is unreachable. Trace data contains sensitive information. Filesystem permissions allow other users to read the fallback directory.

---

## Input Source Coverage

| Input Source | Data Flows | Threats | Validation Points | Responsibility | Gaps |
|-------------|-----------|---------|-------------------|----------------|------|
| User direct input (SDK API calls) | DF1, DF2, DF5, DF8 | T5 | `client.py:Client.__init__` (anonymizer, hide_inputs, hide_outputs params) | User | User must configure anonymizer for PII redaction |
| LangSmith API responses | DF3 | T1, T2 | `client.py:_process_prompt_manifest` (allowed_objects, secrets_from_env) | Shared (SDK validates deserialization, API authenticates users) | Version gap for langchain-core 1.0.0-1.2.4 |
| HTTP headers (distributed tracing) | DF4 | T3 | `run_trees.py:_filter_replica_for_headers` (allowlist filter) | Project | `updates` field passes through filter |
| Configuration (env vars) | DF7 | -- | `utils.py:get_env_var`, `utils.py:get_api_key` (strip/trim) | User (deployer) | -- |
| Sandbox dataplane responses | DF6 | -- | `sandbox/_sandbox.py:Sandbox._run_http` (HTTP status check) | Shared (SDK authenticates, sandbox isolates) | -- |
| Tunnel TCP data | DF10 | -- | `sandbox/_tunnel.py:_read_status` (protocol status check) | User | Tunnel forwards arbitrary TCP; user controls what runs in sandbox |

---

## Out-of-Scope Threats

Threats that appear valid in isolation but fall outside project responsibility because they depend on conditions the project does not control.

| Pattern | Why Out of Scope | Project Responsibility Ends At |
|---------|-----------------|-------------------------------|
| Credential theft via LangSmith API compromise | The SDK authenticates with the API but cannot verify server integrity beyond TLS. A compromised API server could return malicious data. | Authenticating with the configured API key over HTTPS (`client.py:Client.__init__`). TLS certificate validation via `requests`/`httpx`. |
| PII leakage in trace data without anonymizer | The SDK captures whatever the user traces. If function arguments contain PII, it is sent to LangSmith. The SDK provides opt-in anonymizer/redaction but cannot know what is sensitive. | Providing `anonymizer`, `hide_inputs`, `hide_outputs`, `hide_metadata` parameters on `Client.__init__`. Documenting their usage. |
| Prompt injection leading to code execution | If an LLM returns malicious output that is executed by user-registered tools, the SDK is not responsible. The SDK traces LLM calls but does not execute LLM output. | Capturing and serializing trace data. The SDK does not interpret or execute LLM outputs. |
| Sandbox escape / container breakout | The sandbox client sends commands to a remote sandbox service. Container isolation is the server's responsibility. | Authenticating with the sandbox API (`sandbox/_client.py:SandboxClient.__init__`). Validating `dataplane_url` is present. |
| Malicious sandbox commands | Users choose what commands to run in sandboxes. The SDK passes commands through without modification. | Providing the `Sandbox.run()` API. Command content is the user's responsibility. |
| LLM provider API key exfiltration via wrapper | The wrappers (C8) intercept LLM API calls for tracing. The API keys used to call LLM providers are the user's responsibility. The SDK does not log these keys unless the user includes them in traced arguments. | Wrapping LLM API calls for trace capture. Not logging API keys in wrapper code. |
| Man-in-the-middle on non-TLS connections | If a user overrides the API endpoint to use HTTP instead of HTTPS, the SDK cannot protect credentials in transit. | Defaulting to `https://api.smith.langchain.com`. Users who override accept the risk. |
| Environment variable injection | If an attacker can modify the process environment, they can change `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, etc. This is an OS-level security concern. | Reading env vars via `os.environ` (`utils.py:get_env_var`). The SDK cannot control who sets environment variables. |

### Rationale

**PII in traces**: The SDK's responsibility ends at providing redaction tools. The `anonymizer` parameter on `Client.__init__` accepts regex rules or callable processors (`anonymizer.py:create_anonymizer`). The `hide_inputs`/`hide_outputs`/`hide_metadata` callbacks provide additional control. Users who trace sensitive data without configuring these features are operating outside the SDK's security boundary.

**Prompt injection**: The SDK is an observability tool, not an execution engine. It captures trace data but does not interpret LLM outputs. If a user's application executes LLM-suggested code, that is the application's responsibility, not the SDK's.

**Sandbox operations**: The SDK is a thin client for the sandbox API. It passes commands (`Sandbox.run(command)`), files (`Sandbox.write(path, content)`), and tunnel configurations through to the remote dataplane. The SDK authenticates with the sandbox service but does not sandbox anything locally.

---

## Investigated and Dismissed

| ID | Original Threat | Investigation | Evidence | Conclusion |
|----|----------------|---------------|----------|------------|
| D1 | SSRF via tracing header injection (GHSA-v34v-rq6j-cj6p) | Verified that `_filter_replica_for_headers` strips `api_url`, `api_key`, and `auth` from header-supplied replicas. Legacy tuple format hardcodes `api_url=None`. Env var path correctly allows `api_url` (deployer-controlled). Replicas not re-serialized in outgoing headers. | `run_trees.py:_filter_replica_for_headers` (lines 63-70), `run_trees.py:_Baggage.from_header` (lines 1003-1030), `run_trees.py:_Baggage.to_header` (lines 1047-1064) | Fix is complete. Attacker cannot redirect trace data to an arbitrary endpoint via the `baggage` header. All header-reachable code paths are covered. |
| D2 | API key exfiltration via crafted prompt secret fields | Verified that `secrets_from_env` defaults to `False` in both `Client.pull_prompt()` and `AsyncClient.pull_prompt()`. When `False`, `langchain_core.load.load()` does not read environment variables for secret fields. | `client.py:Client.pull_prompt` (line 9191, `secrets_from_env: bool = False`), `async_client.py:AsyncClient.pull_prompt` | Fix is complete for GHSA-c67j-w6g6-q2cm. Environment variables are not exfiltrated by default. |
| D3 | Arbitrary Python object deserialization via prompt pull (default path) | Verified that `allowed_objects="core"` restricts deserialization to `langchain_core` types only. Combined with jinja2 template blocking and `Serializable` subclass check in `langchain_core.load.load()`, the default path has a narrow attack surface. | `client.py:_process_prompt_manifest` (line 338), `langchain_core/load/load.py:Reviver.__call__` (allowlist check) | Default path (`include_model=False`) is adequately protected with current `langchain_core` versions. Residual risk limited to theoretical side effects in core type constructors. |

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-04-07 | generated by langster-threat-model (deep mode) | Initial threat model |
