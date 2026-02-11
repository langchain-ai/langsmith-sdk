/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import throws an error in internal CJS build, but seems to work fine after build
import { DefaultReporter } from "vitest/reporters";

import { printVitestTestModulesReporterTable } from "./utils/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  // Override uses the Reporter interface signature which receives params,
  // but DefaultReporter narrows it to no params. We suppress the TS error
  // since vitest calls this method with the full Reporter signature at runtime.
  // @ts-expect-error vitest Reporter interface passes (testModules, errors, reason)
  async onTestRunEnd(
    testModules: ReadonlyArray<{
      children: {
        allTests: () => Iterable<{
          name: string;
          result: () => { state: "pending" | "passed" | "failed" | "skipped" };
          diagnostic: () => { duration: number } | undefined;
        }>;
      };
      state: () => string;
      moduleId: string;
    }>,
    _unhandledErrors: ReadonlyArray<unknown>,
    _reason: "passed" | "interrupted" | "failed"
  ) {
    super.onTestRunEnd();
    await printVitestTestModulesReporterTable(testModules);
  }
}

export default LangSmithEvalReporter;
