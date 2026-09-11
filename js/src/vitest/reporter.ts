/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import throws an error in internal CJS build, but seems to work fine after build
import { DefaultReporter } from "vitest/reporters";

import { RunnerTestFile } from "vitest";
import {
  printVitestReporterTable,
  printVitestTestModulesReporterTable,
} from "./utils/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  private skipOnFinished = false;

  async onFinished(files: RunnerTestFile[], errors: unknown[]) {
    const onFinished = (
      DefaultReporter.prototype as unknown as {
        onFinished?: (files: RunnerTestFile[], errors: unknown[]) => void;
      }
    ).onFinished;
    onFinished?.call(this, files, errors);
    if (this.skipOnFinished) return;
    await printVitestReporterTable(files, this.ctx);
  }

  async onTestRunEnd(...args: Parameters<DefaultReporter["onTestRunEnd"]>) {
    super.onTestRunEnd(...args);
    this.skipOnFinished = true;
    await printVitestTestModulesReporterTable(args[0]);
  }
}

export default LangSmithEvalReporter;
