# Files

- [Evaluation and Experiment Workflows](evaluation-and-experiments.md) - How the JavaScript and Python SDKs create or reuse experiments, schedule predictions and evaluators, attribute feedback, order results, and handle failures and trace delivery.
- [Sandbox Lifecycle, Files, Services, and Command Execution](sandbox-lifecycle-and-execution.md) - End-to-end guide to sandbox lifecycle, runtime configuration, files, mounts, delegated access, service URLs, token verification, and HTTP, WebSocket, and SSE command transports in the Python and JavaScript SDKs.
- [Trace Capture, Transformation, and Ingestion](trace-capture-and-ingestion.md) - End-to-end Python and JavaScript trace lifecycle across direct, queued, compressed, SDK-to-OpenTelemetry, and native OpenTelemetry ingestion routes, including execution ownership, retries, failure, flush, and shutdown.
- [Measured Trace Ingestion Paths](trace-ingestion-measured.md) - Durable timing capture comparing bulk trace-ingestion routes through direct, batched, multipart, compressed, OpenTelemetry, and hybrid paths. Preserves call counts, wire sizes, thread handoffs, flush boundaries, and per-path event timelines.
