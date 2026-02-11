/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import throws an error in internal CJS build, but seems to work fine after build
import { DefaultReporter } from "vitest/reporters";

import { printVitestTestModulesReporterTable } from "./utils/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async onTestRunEnd(testModules: any, unhandledErrors: any, reason: any) {
    super.onTestRunEnd(testModules, unhandledErrors, reason);
    await printVitestTestModulesReporterTable(testModules);
  }
}

export default LangSmithEvalReporter;
