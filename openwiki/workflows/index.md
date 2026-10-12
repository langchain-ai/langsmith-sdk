# Files

- [Evaluation and Experiment Workflows](evaluation-and-experiments.md) - How LangSmith SDK evaluation resolves datasets and experiments, schedules predictions and scoring, aligns results, records feedback, and finalizes evaluation projects.
- [Sandbox Lifecycle and Execution Transports](sandbox-lifecycle-and-execution.md) - Control-plane and dataplane lifecycle for LangSmith sandboxes, including mounts, files, snapshots, service access, cleanup, and the distinct HTTP, WebSocket, SSE, and Python tunnel paths.
- [Trace Capture, Transformation, and Ingestion](trace-capture-and-ingestion.md) - End-to-end Python and JavaScript trace lifecycle across direct, queued, compressed, SDK OpenTelemetry, and native OpenTelemetry ingestion routes, including endpoint resolution, I/O ownership, retries, failures, flush, and shutdown.
- [Measured Trace Ingestion Paths](trace-ingestion-measured.md) - Historical trace-lab measurements for direct, batched, multipart, compressed, OpenTelemetry, and hybrid ingestion. Preserves the recorded values while separating capture-specific observations from current endpoint and lifecycle semantics.
