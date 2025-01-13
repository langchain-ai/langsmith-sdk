/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import does not to work with our CJS build order
import { DefaultReporter, type TestModule } from "vitest/reporters";

import { RunnerTestFile } from "vitest";
import { printReporterTable } from "../utils/jestlike/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  async onFinished(files: RunnerTestFile[], errors: unknown[]) {
    super.onFinished(files, errors);
    for (const file of files) {
      const testModule = this.ctx.state.getReportedEntity(file) as TestModule;
      const tests = [...testModule.children.allTests()].map((test) => {
        return {
          title: test.name,
          status: test.result()?.state ?? "skipped",
          duration: Math.round(test.diagnostic()?.duration ?? 0),
        };
      });
      await printReporterTable(tests);
    }
    this.end = performance.now();
  }
}

export default LangSmithEvalReporter;
