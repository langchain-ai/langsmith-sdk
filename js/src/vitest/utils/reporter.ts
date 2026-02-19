import { printReporterTable } from "../../utils/jestlike/reporter.js";

// Can't use types here because of module resolution issues
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const printVitestReporterTable = async (files: any, ctx: any) => {
  for (const file of files) {
    for (const task of file.tasks) {
      const testModule = ctx.state.getReportedEntity(task);
      const tests = [...testModule.children.allTests()].map((test) => {
        return {
          title: test.name,
          status: test.result()?.state ?? "skipped",
          duration: Math.round(test.diagnostic()?.duration ?? 0),
        };
      });
      const result = ["pass", "fail", "skip"].includes(task.result?.state ?? "")
        ? task.result?.state
        : "skip";
      await printReporterTable(task.name, tests, result);
    }
  }
};

export const printVitestTestModulesReporterTable = async (
  testModules: ReadonlyArray<{
    children: {
      allTests: () => Iterable<{
        name: string;
        result: () => { state: "pending" | "passed" | "failed" | "skipped" };
        diagnostic: () => { duration: number } | undefined;
      }>;
    };
    state: () => string;
    relativeModuleId: string;
  }>
) => {
  for (const testModule of testModules) {
    const tests = [...testModule.children.allTests()].map((test) => {
      return {
        title: test.name,
        status: test.result()?.state ?? "skipped",
        duration: Math.round(test.diagnostic()?.duration ?? 0),
      };
    });

    const moduleState = testModule.state();
    const testStatus =
      moduleState === "passed" ||
      moduleState === "failed" ||
      moduleState === "skipped"
        ? moduleState
        : "skip";

    await printReporterTable(testModule.relativeModuleId, tests, testStatus);
  }
};
