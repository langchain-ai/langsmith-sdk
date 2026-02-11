/* eslint-disable import/no-extraneous-dependencies */

import { printVitestTestModulesReporterTable } from "./utils/reporter.js";
import { importVitestModule } from "./utils/esm.mjs";

const vitestReporters = await importVitestModule("reporters");
const DefaultReporter = vitestReporters.DefaultReporter;

class LangSmithEvalReporter extends DefaultReporter {
  async onTestRunEnd(
    testModules: ReadonlyArray<unknown>,
    _unhandledErrors: ReadonlyArray<unknown>,
    _reason: "passed" | "interrupted" | "failed"
  ) {
    super.onTestRunEnd();
    await printVitestTestModulesReporterTable(
      testModules as ReadonlyArray<{
        children: {
          allTests: () => Iterable<{
            name: string;
            result: () => {
              state: "pending" | "passed" | "failed" | "skipped";
            };
            diagnostic: () => { duration: number } | undefined;
          }>;
        };
        state: () => "skipped" | "passed" | "failed" | "pending" | "queued";
        moduleId: string;
      }>
    );
  }
}

export default LangSmithEvalReporter;
