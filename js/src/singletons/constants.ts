export const _LC_CONTEXT_VARIABLES_KEY = Symbol.for("lc:context_variables");

export const _LC_CHILD_RUN_END_PROMISES_KEY = Symbol.for(
  "lc:child_run_end_promises",
);

export const _REPLICA_TRACE_ROOTS_KEY = Symbol.for(
  "langsmith:replica_trace_roots",
);

// Marker for a payload whose redactor threw.
// Takes the hook name, never the error: reading e.constructor runs user code.
export const _PROCESSING_FAILED_KEY = "ls_error";
export const _PROCESSING_FAILED_PREFIX = "Processing failed; ";
export const _processingFailed = (
  payload: "inputs" | "outputs",
  hook: string,
): string => `${_PROCESSING_FAILED_PREFIX}${payload} dropped (${hook})`;
