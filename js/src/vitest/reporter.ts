/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import throws an error in internal CJS build, but seems to work fine after build
import { DefaultReporter } from "vitest/node";

import { printVitestTestModulesReporterTable } from "./utils/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  async onTestRunEnd(...args: Parameters<DefaultReporter["onTestRunEnd"]>) {
    super.onTestRunEnd(...args);
    await printVitestTestModulesReporterTable(args[0]);
  }
}

export default LangSmithEvalReporter;
