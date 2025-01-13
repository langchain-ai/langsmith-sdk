import { Table } from "console-table-printer";
import chalk from "chalk";

import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs/promises";
import { EvaluationResult } from "../../evaluation/evaluator.js";
import { ScoreType } from "../../schemas.js";

const RESERVED_KEYS = ["Name", "Result", "Inputs", "Expected", "Actual"];

function formatTestName(name: string, duration: number) {
  if (duration != null) {
    return `${name} (${duration}ms)`;
  } else {
    return name;
  }
}

function getFormattedStatus(status: string) {
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

function getColorParam(status: string) {
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

function formatValue(value: unknown) {
  if (typeof value === "object" && value !== null) {
    return Object.entries(value)
      .map(([k, v]) => {
        const rawValue = typeof v === "string" ? v : JSON.stringify(v);
        const value =
          rawValue.length > 32 ? rawValue.slice(0, 29) + "..." : rawValue;
        return `${k}: ${value}`;
      })
      .join(", ");
  }
  if (value == null) {
    return;
  }
  return String(value);
}

export async function printReporterTable(
  results: { title: string; duration: number; status: string }[],
  failureMessage?: string
) {
  const rows = [];
  const feedbackKeys = new Set<string>();
  let experimentUrl;
  for (const result of results) {
    const { title, duration, status } = result;
    const titleComponents = title.split(":");
    const testId =
      titleComponents.length > 1 && !isNaN(parseInt(titleComponents[0], 10))
        ? titleComponents[0]
        : undefined;
    const testName =
      testId !== undefined
        ? titleComponents.slice(1).join(":").trim()
        : titleComponents.join(":");
    // Non-LangSmith test
    if (testId === undefined) {
      rows.push([
        {
          Name: formatTestName(testName, duration),
          Status: getFormattedStatus(status),
        },
        getColorParam(status),
      ]);
    } else if (status === "pending") {
      // Skipped
      rows.push([
        {
          Name: formatTestName(testName, duration),
          Status: getFormattedStatus(status),
        },
        getColorParam(status),
      ]);
    } else {
      const resultsPath = path.join(
        os.tmpdir(),
        "langsmith_test_results",
        `${testId}.json`
      );
      let fileContent;
      try {
        fileContent = JSON.parse(await fs.readFile(resultsPath, "utf-8"));
        await fs.unlink(resultsPath);
      } catch (e) {
        throw new Error("Failed to display custom evaluation results.");
      }
      const feedback = fileContent.feedback.reduce(
        (acc: Record<string, ScoreType>, current: EvaluationResult) => {
          if (
            !RESERVED_KEYS.includes(current.key) &&
            current.score !== undefined
          ) {
            feedbackKeys.add(current.key);
            acc[current.key] = current.score;
          }
          return acc;
        },
        {}
      );
      experimentUrl = experimentUrl ?? fileContent.experimentUrl;
      rows.push([
        {
          Name: formatTestName(testName, duration),
          Inputs: formatValue(fileContent.inputs),
          "Reference Outputs": formatValue(fileContent.expected),
          Outputs: formatValue(fileContent.outputs),
          Status: getFormattedStatus(status),
          ...feedback,
        },
        getColorParam(status),
      ]);
    }
  }

  for (const key of feedbackKeys) {
    const scores = rows
      .map(([row]) => row[key])
      .filter((score) => score !== undefined);
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
          } else if (deviation < -0.5) {
            coloredScore = chalk.red(score);
          } else if (deviation < 0) {
            coloredScore = chalk.yellow(score);
          } else if (deviation === 0) {
            coloredScore = chalk.white(score);
          } else if (deviation <= 0.5) {
            coloredScore = chalk.green(score);
          } else {
            coloredScore = chalk.greenBright(score);
          }
          row[0][key] = coloredScore;
        }
      }
    }
  }

  console.log();
  const table = new Table({
    columns: [
      { name: "Name", alignment: "left", maxLen: 48 },
      { name: "Inputs", alignment: "left" },
      { name: "Reference Outputs", alignment: "left" },
      { name: "Outputs", alignment: "left" },
      { name: "Status", alignment: "left" },
    ],
    colorMap: {
      grey: "\x1b[90m",
    },
  });
  for (const row of rows) {
    table.addRow(row[0], row[1]);
  }
  if (failureMessage) {
    console.log(failureMessage);
  }
  table.printTable();
  if (experimentUrl) {
    console.log();
    console.log(
      ` [LANGSMITH]: View full results in LangSmith at ${experimentUrl}`
    );
    console.log();
  }
}
