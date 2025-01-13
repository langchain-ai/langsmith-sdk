/* eslint-disable import/no-extraneous-dependencies */
import { DefaultReporter } from "@jest/reporters";

import { printReporterTable } from "../utils/jestlike/reporter.js";

class LangSmithEvalReporter extends DefaultReporter {
  async onTestResult(test: any, testResult: any, aggregatedResults: any) {
    try {
      await printReporterTable(
        testResult.testResults,
        testResult.failureMessage
      );
    } catch (e: any) {
      console.log("Failed to display LangSmith eval results:", e.message);
      return super.onTestResult(test, testResult, aggregatedResults);
    }
  }
}

export default LangSmithEvalReporter;
