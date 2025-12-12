// eslint-disable-next-line import/no-extraneous-dependencies
import { type LoadEvaluatorOptions, loadEvaluator } from "langchain/evaluation";
import type { Run, Example } from "../schemas.js";
import { getLangchainCallbacks } from "../langchain.js";

function isStringifiable(
  value: unknown
): value is string | number | boolean | bigint {
  return (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  );
}

// utility methods for extracting stringified values
// from unknown inputs and records
function getPrimitiveValue(value: unknown) {
  if (isStringifiable(value)) return String(value);
  if (!Array.isArray(value) && typeof value === "object" && value != null) {
    const values = Object.values(value);
    if (values.length === 1 && isStringifiable(values[0])) {
      return String(values[0]);
    }
  }
  return undefined;
}
