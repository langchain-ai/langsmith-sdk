import { DefaultReporter } from "@jest/reporters";
import { Table } from "console-table-printer";
import { validate as isUUID } from "uuid";
import chalk from 'chalk';

import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs/promises";

const RESERVED_KEYS = ["Name", "Result", "Inputs", "Expected", "Actual"];

function formatTestName(name, duration) {
  if (duration != null) {
    return `${name} (${duration}ms)`
  } else {
    return name;
  }
}

function getFormattedStatus(status) {
  const s = status.toLowerCase();
  if (s === "pending") {
    return chalk.yellow("○ Skipped");
  } else if (s === "passed") {
    return chalk.green("✓ Passed");
  } else if (s === "failed") {
    return chalk.red("✕ Failed");
  } else {
    return status;
  }
}

function getColorParam(status) {
  const s = status.toLowerCase();
  if (s === "pending") {
    return { color: "yellow" };
  } else if (s === "passed") {
    return { color: "grey" };
  } else if (s === "failed") {
    return { color: "red" };
  } else {
    return {};
  }
}

function formatValue(value) {
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value)
      .map(([k, v]) => {
        const rawValue = typeof v === 'string' ? v : JSON.stringify(v);
        const value = rawValue.length > 32 ? (rawValue.slice(0, 29) + "...") : rawValue;
        return `${k}: ${value}`;
      })
      .join(', ');
  }
  if (value == null) {
    return;
  }
  return String(value);
}

class CustomReporter extends DefaultReporter {
  async onTestResult(
    test,
    testResult,
    aggregatedResults
  ) {
    const rows = [];
    const feedbackKeys = new Set();
    try {
      for (const result of testResult.testResults) {
        const { title } = result;
        const titleComponents = title.split(":");
        const testId = titleComponents.length > 1 && !isNaN(parseInt(titleComponents[0], 10)) ? titleComponents[0] : undefined;
        const testName = testId !== undefined ? titleComponents.slice(1).join(":").trim() : titleComponents.join(":");
        // Non-LangSmith test
        if (testId === undefined) {
          rows.push([{
            Name: formatTestName(testName, result.duration),
            Result: getFormattedStatus(result.status),
          }, getColorParam(result.status)]);
        } else if (result.status === "pending") {
          // Skipped
          rows.push([{
            Name: formatTestName(testName, result.duration),
            Result: getFormattedStatus(result.status),
          }, getColorParam(result.status)]);
        } else {
          const resultsPath = path.join(
            os.tmpdir(),
            "langsmith_test_results",
            `${testId}.json`
          );
          let fileContent;
          try {
            fileContent = JSON.parse(await fs.readFile(resultsPath));
          } catch (e) {
            throw new Error("Failed to display custom evaluation results. Falling back to default display...")
          }
          const feedback = fileContent.feedback.reduce((acc, current) => {
            if (!RESERVED_KEYS.includes(current.key)) {
              feedbackKeys.add(current.key);
              acc[current.key] = current.score;
            }
            return acc;
          }, {});
          rows.push([{
            Name: formatTestName(testName, result.duration),
            Result: getFormattedStatus(result.status),
            Inputs: formatValue(fileContent.inputs),
            Expected: formatValue(fileContent.expected),
            Actual: formatValue(fileContent.outputs),
            ...feedback,
          }, getColorParam(result.status)]);
        }      
      }
    } catch (e) {
      console.log(e.message);
      return super.onTestResult(test, testResult, aggregatedResults);
    }
    
    for (const key of feedbackKeys) {
      const scores = rows
        .map(([row]) => row[key])
        .filter(score => score !== undefined);
      if (scores.length > 0) {
        const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
        const stdDev = Math.sqrt(
          scores.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / scores.length
        );
        for (const row of rows) {
          const score = row[0][key];
          if (score !== undefined) {
            const deviation = (score - mean) / stdDev;
            let coloredScore;
            if (isNaN(deviation)) {
              coloredScore = chalk.white(score);
            } else if (deviation <= -1) {
              coloredScore = chalk.redBright(score);
            } else if (deviation < -.5) {
              coloredScore = chalk.red(score);
            } else if (deviation < 0) {
              coloredScore = chalk.yellow(score);
            } else if (deviation === 0) {
              coloredScore = chalk.white(score);
            } else if (deviation <= .5) {
              coloredScore = chalk.green(score);
            } else {
              coloredScore = chalk.greenBright(score);
            }
            row[0][key] = coloredScore;
          }
        }
      }
    }

    console.log("");
    const table = new Table({
      colorMap: {
        grey: "\x1b[90m",
      },
    });
    for (const row of rows) {
      table.addRow(...row);
    }
    if (testResult.failureMessage) {
      console.log(testResult.failureMessage);
    }
    table.printTable();
  }
}

export default CustomReporter;
