export const _LC_CONTEXT_VARIABLES_KEY = Symbol.for("lc:context_variables");

export const _LC_CHILD_RUN_END_PROMISES_KEY = Symbol.for(
  "lc:child_run_end_promises",
);

export const _REPLICA_TRACE_ROOTS_KEY = Symbol.for(
  "langsmith:replica_trace_roots",
);

export const _PROCESSING_FAILED_KEY = "ls_error";
export const _PROCESSING_FAILED_PREFIX = "Processing failed; ";

/**
 * Build the marker that replaces a payload whose redactor threw.
 *
 * Carries the error type, never its message: an error routinely echoes the
 * payload it was reading (`KeyError: 'secret'`), so the full text goes to the
 * console and is never uploaded. `constructor.name` is assignable, hence the
 * identifier check.
 */
export const _processingFailed = (
  payload: "inputs" | "outputs",
  e: unknown,
): string => {
  const raw = String(
    (typeof e === "object" && e !== null && e.constructor?.name) || typeof e,
  );
  const kind = /^\w{1,64}$/.test(raw) ? raw : "unknown";
  const hook = payload === "inputs" ? "processInputs" : "processOutputs";
  return `${_PROCESSING_FAILED_PREFIX}${payload} dropped (${hook}: ${kind})`;
};
