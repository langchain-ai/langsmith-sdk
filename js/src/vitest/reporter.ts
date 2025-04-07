/* eslint-disable import/no-extraneous-dependencies */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore Import throws an error in internal CJS build, but seems to work fine after build
import { DefaultReporter, type TestModule } from "vitest/reporters";

import { RunnerTestFile } from "vitest";
import { printReporterTable } from "../utils/jestlike/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  async onFinished(files: RunnerTestFile[], errors: unknown[]) {
    super.onFinished(files, errors);
    for (const file of files) {
      for (const task of file.tasks) {
        const testModule = this.ctx.state.getReportedEntity(task) as TestModule;
        const tests = [...testModule.children.allTests()].map((test) => {
          return {
            title: test.name,
            status: test.result()?.state ?? "skipped",
            duration: Math.round(test.diagnostic()?.duration ?? 0),
          };
        });
        const result = ["pass", "fail", "skip"].includes(
          task.result?.state ?? ""
        )
          ? (task.result?.state as "pass" | "fail" | "skip")
          : "skip";
        await printReporterTable(task.name, tests, result);
      }
    }
  }
}

export default LangSmithEvalReporter;
