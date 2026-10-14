import { expect, test, vi } from "vitest";
import LangSmithEvalReporter from "../vitest/reporter.js";
import { printReporterTable } from "../utils/jestlike/reporter.js";
import { printVitestTestModulesReporterTable } from "../vitest/utils/reporter.js";

vi.mock("vitest/reporters", () => ({
  DefaultReporter: class {
    onTestRunEnd() {}
  },
}));

vi.mock("../utils/jestlike/reporter.js", () => ({
  printReporterTable: vi.fn(),
}));

test("reports iterable Vitest 4 results once when both lifecycle hooks run", async () => {
  vi.mocked(printReporterTable).mockClear();
  const modules = [
    {
      relativeModuleId: "eval.test.ts",
      state: () => "passed" as const,
      children: {
        *allTests() {
          for (const state of ["passed", "failed", "skipped"] as const) {
            yield {
              name: state,
              result: () => ({ state }),
              diagnostic: () => undefined,
            };
          }
        },
      },
    },
  ];
  const reporter = new LangSmithEvalReporter();
  await reporter.onTestRunEnd(
    modules as unknown as Parameters<typeof reporter.onTestRunEnd>[0],
    [],
    "passed",
  );
  await reporter.onFinished([], []);
  expect(printReporterTable).toHaveBeenCalledExactlyOnceWith(
    "eval.test.ts",
    [
      { title: "passed", status: "passed", duration: 0 },
      { title: "failed", status: "failed", duration: 0 },
      { title: "skipped", status: "skipped", duration: 0 },
    ],
    "passed",
  );
});

test.each(["pending", "queued"] as const)(
  "reports %s modules as skipped",
  async (state) => {
    vi.mocked(printReporterTable).mockClear();
    await printVitestTestModulesReporterTable([
      {
        relativeModuleId: "eval.test.ts",
        state: () => state,
        children: { allTests: () => [] },
      },
    ]);
    expect(printReporterTable).toHaveBeenCalledExactlyOnceWith(
      "eval.test.ts",
      [],
      "skipped",
    );
  },
);
