# Files

- [Evaluation and Experiment Workflows](evaluation-and-experiments.md) - How LangSmith SDK evaluation turns datasets or existing experiments into prediction runs, row and summary feedback, comparative scores, and streamed or uploaded results.
- [Sandbox Lifecycle, Files, Tunnels, and Command Execution](sandbox-lifecycle-and-execution.md) - End-to-end lifecycle of LangSmith sandboxes from control-plane creation through dataplane files, Python TCP tunnels, HTTP and WebSocket commands, reconnect offsets, snapshots, and cleanup.
- [Trace Capture, Transformation, and Ingestion](trace-capture-and-ingestion.md) - End-to-end Python and JavaScript trace lifecycle, including direct, queued JSON, multipart, compressed, SDK-to-OpenTelemetry, and native OpenTelemetry ingestion routes. Compares routing, transformation, execution context, retries, failures, and flush behavior.
- [Measured Trace Ingestion Paths](trace-ingestion-measured.md) - Durable timing capture comparing bulk trace-ingestion routes through direct, batched, multipart, compressed, OpenTelemetry, and hybrid paths. Preserves call counts, wire sizes, thread handoffs, flush boundaries, and per-path event timelines.
