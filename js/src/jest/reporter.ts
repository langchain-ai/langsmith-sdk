/* eslint-disable import/no-extraneous-dependencies */
import { DefaultReporter } from "@jest/reporters";

import { printReporterTable } from "../utils/jestlike/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  async onTestResult(test: any, testResult: any, aggregatedResults: any) {
    if (testResult.failureMessage) {
      console.log(testResult.failureMessage);
    }
    const groupedTestResults = testResult.testResults.reduce(
      (groups: Record<string, any>, testResult: any) => {
        const ancestorTitle = testResult.ancestorTitles.join(" > ");
        if (groups[ancestorTitle] === undefined) {
          groups[ancestorTitle] = [];
        }
        groups[ancestorTitle].push(testResult);
        return groups;
      },
      {}
    );
    try {
      for (const testGroupName of Object.keys(groupedTestResults)) {
        const resultGroup = groupedTestResults[testGroupName];
        const unskippedTests = resultGroup.filter(
          (result: any) => result.status !== "pending"
        );
        const overallResult =
          unskippedTests.length === 0
            ? "skip"
            : unskippedTests.every((result: any) => result.status === "passed")
            ? "pass"
            : "fail";
        await printReporterTable(testGroupName, resultGroup, overallResult);
      }
    } catch (e: any) {
      console.log("Failed to display LangSmith eval results:", e.message);
      super.onTestResult(test, testResult, aggregatedResults);
    }
  }
}

export default LangSmithEvalReporter;
