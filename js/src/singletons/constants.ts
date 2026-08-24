export const _LC_CONTEXT_VARIABLES_KEY = Symbol.for("lc:context_variables");

export const _LC_CHILD_RUN_END_PROMISES_KEY = Symbol.for(
  "lc:child_run_end_promises",
);

export const _REPLICA_TRACE_ROOTS_KEY = Symbol.for(
  "langsmith:replica_trace_roots",
);

// Replaces a payload whose redactor threw. Static text: an error can echo it.
export const _PROCESSING_FAILED_KEY = "ls_error";
export const _INPUTS_PROCESSING_FAILED =
  "processInputs failed; inputs were dropped to avoid logging unprocessed data";
export const _OUTPUTS_PROCESSING_FAILED =
  "processOutputs failed; outputs were dropped to avoid logging unprocessed data";
