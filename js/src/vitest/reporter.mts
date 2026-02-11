/* eslint-disable import/no-extraneous-dependencies */

import { printVitestTestModulesReporterTable } from "./utils/reporter.js";
import { importVitestModule } from "./utils/esm.mjs";

const vitestReporters = await importVitestModule("reporters");
const DefaultReporter = vitestReporters.DefaultReporter;

class LangSmithEvalReporter extends DefaultReporter {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async onTestRunEnd(testModules: any, unhandledErrors: any, reason: any) {
    super.onTestRunEnd(testModules, unhandledErrors, reason);
    await printVitestTestModulesReporterTable(testModules);
  }
}

export default LangSmithEvalReporter;
