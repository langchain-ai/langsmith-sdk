/* eslint-disable import/no-extraneous-dependencies */

import { printVitestTestModulesReporterTable } from "./utils/reporter.js";
import { importVitestModule } from "./utils/esm.mjs";

const vitestReporters = await importVitestModule("reporters");
const DefaultReporter = vitestReporters.DefaultReporter;

class LangSmithEvalReporter extends DefaultReporter {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onTestRunEnd(...args: any[]): any {
    super.onTestRunEnd(...(args as [any, any, any]));
    return printVitestTestModulesReporterTable(args[0]);
  }
}

export default LangSmithEvalReporter;
