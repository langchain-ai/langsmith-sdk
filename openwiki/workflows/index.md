# Files

- [Evaluation and Experiment Workflows](evaluation-and-experiments.md) - How the JavaScript and Python LangSmith SDKs orchestrate new-target, existing-experiment, and comparative evaluation, including scheduling, tracing, feedback, failures, and result consumption.
- [Sandbox Lifecycle, Access, Services, and Command Execution](sandbox-lifecycle-and-execution.md) - Cross-SDK workflow for creating, securing, accessing, executing in, snapshotting, and cleaning up LangSmith sandboxes across the control plane and dataplane.
- [Trace Capture, Transformation, and Ingestion](trace-capture-and-ingestion.md) - End-to-end Python and JavaScript trace lifecycle, including direct, queued JSON, multipart, compressed, SDK-to-OpenTelemetry, and native OpenTelemetry ingestion routes. Compares routing, transformation, execution context, retries, failures, and flush behavior.
- [Measured Trace Ingestion Paths](trace-ingestion-measured.md) - Durable timing capture comparing bulk trace-ingestion routes through direct, batched, multipart, compressed, OpenTelemetry, and hybrid paths. Preserves call counts, wire sizes, thread handoffs, flush boundaries, and per-path event timelines.
