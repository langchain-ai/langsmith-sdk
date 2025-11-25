/* eslint-disable import/no-extraneous-dependencies */

import {
  printVitestReporterTable,
  printVitestTestModulesReporterTable,
  type VitestTestModule,
} from "./utils/reporter.js";
import { importVitestModule } from "./utils/esm.mjs";

const vitestReporters = await importVitestModule("reporters");
const DefaultReporter = vitestReporters.DefaultReporter;

class LangSmithEvalReporter extends DefaultReporter {
  async onFinished(files: unknown[], errors: unknown[]) {
    super.onFinished(files, errors);
    await printVitestReporterTable(files, this.ctx);
  }

  // `onFinished` is removed in Vitest 4.x, so we use `onTestRunEnd` instead.
  async onTestRunEnd(
    testModules: VitestTestModule[],
    unhandledErrors: { message: string; name?: string }[],
    reason: "passed" | "interrupted" | "failed"
  ) {
    super.onTestRunEnd(testModules, unhandledErrors, reason);
    await printVitestTestModulesReporterTable(testModules);
  }
}

export default LangSmithEvalReporter;
