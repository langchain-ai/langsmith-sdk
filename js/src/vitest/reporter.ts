/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import throws an error in internal CJS build, but seems to work fine after build
import { DefaultReporter } from "vitest/reporters";

import { RunnerTestFile } from "vitest";
import { printVitestReporterTable } from "./utils.js";

class LangSmithEvalReporter extends DefaultReporter {
  async onFinished(files: RunnerTestFile[], errors: unknown[]) {
    super.onFinished(files, errors);
    await printVitestReporterTable(files, this.ctx);
  }
}

export default LangSmithEvalReporter;
