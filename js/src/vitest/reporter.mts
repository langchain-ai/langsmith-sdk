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
  private skipOnFinished = false;

  async onFinished(files: unknown[], errors: unknown[]) {
    super.onFinished(files, errors);

    // Vitest 3.x will call `onFinished` after `onTestRunEnd`,
    // thus we need to gate this to avoid double printing.
    if (this.skipOnFinished) return;
    await printVitestReporterTable(files, this.ctx);
  }

  // `onFinished` is removed in Vitest 4.x, so we use `onTestRunEnd` instead.
  async onTestRunEnd(
    testModules: VitestTestModule[],
    unhandledErrors: { message: string; name?: string }[],
    reason: "passed" | "interrupted" | "failed"
  ) {
    super.onTestRunEnd(testModules, unhandledErrors, reason);
    this.skipOnFinished = true;
    await printVitestTestModulesReporterTable(testModules);
  }
}

export default LangSmithEvalReporter;
