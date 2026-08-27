export const _LC_CONTEXT_VARIABLES_KEY = Symbol.for("lc:context_variables");

export const _LC_CHILD_RUN_END_PROMISES_KEY = Symbol.for(
  "lc:child_run_end_promises",
);

export const _REPLICA_TRACE_ROOTS_KEY = Symbol.for(
  "langsmith:replica_trace_roots",
);

// Marker for a payload whose redactor threw.
// No error type: reading e.constructor runs user code that can throw in turn.
export const _PROCESSING_FAILED_KEY = "ls_error";
export const _PROCESSING_FAILED_PREFIX = "Processing failed; ";
export const _INPUTS_PROCESSING_FAILED = `${_PROCESSING_FAILED_PREFIX}inputs dropped (processInputs)`;
export const _OUTPUTS_PROCESSING_FAILED = `${_PROCESSING_FAILED_PREFIX}outputs dropped (processOutputs)`;
