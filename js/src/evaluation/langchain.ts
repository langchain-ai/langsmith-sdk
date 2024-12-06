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

/**
 * @deprecated Use `evaluate` instead.
 *
 * This utility function loads a LangChain string evaluator and returns a function
 * which can be used by newer `evaluate` function.
 *
 * @param type Type of string evaluator, one of "criteria" or "labeled_criteria
 * @param options Options for loading the evaluator
 * @returns Evaluator consumable by `evaluate`
 */
export async function getLangchainStringEvaluator(
  type: "criteria" | "labeled_criteria",
  options: LoadEvaluatorOptions & {
    formatEvaluatorInputs?: (
      run: Run,
      example: Example
    ) => { prediction: string; reference?: string; input?: string };
  }
) {
  const evaluator = await loadEvaluator(type, options);
  const feedbackKey = getPrimitiveValue(options.criteria) ?? type;

  const formatEvaluatorInputs =
    options.formatEvaluatorInputs ??
    ((run: Run, example: Example) => {
      const prediction = getPrimitiveValue(run.outputs);
      const reference = getPrimitiveValue(example.outputs);
      const input = getPrimitiveValue(example.inputs);

      if (prediction == null) throw new Error("Missing prediction");
      if (type === "criteria") return { prediction, input };
      return { prediction, reference, input };
    });

  return async (run: Run, example: Example) => {
    const score = await evaluator.evaluateStrings(
      formatEvaluatorInputs(run, example),
      { callbacks: await getLangchainCallbacks() }
    );

    return { key: feedbackKey, ...score };
  };
}
