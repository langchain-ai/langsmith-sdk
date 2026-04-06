import { Table } from "console-table-printer";

import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs/promises";
import { SimpleEvaluationResult } from "./types.js";
import { ScoreType } from "../../schemas.js";
import { STRIP_ANSI_REGEX, TEST_ID_DELIMITER } from "./constants.js";

function getColorLevel(): number {
  const env = process.env;

  if ("NO_COLOR" in env || env.FORCE_COLOR === "false") return 0;
  if ("FORCE_COLOR" in env) {
    return env.FORCE_COLOR!.length === 0
      ? 1
      : Math.min(Number.parseInt(env.FORCE_COLOR!, 10) || 1, 3);
  }

  // CI environments that support color
  if ("CI" in env) {
    if (
      ["GITHUB_ACTIONS", "GITEA_ACTIONS", "CIRCLECI"].some((k) => k in env)
    ) {
      return 1;
    }
    if (
      ["TRAVIS", "APPVEYOR", "GITLAB_CI", "BUILDKITE", "DRONE"].some(
        (k) => k in env
      )
    ) {
      return 1;
    }
    return 0;
  }

  if (env.TERM === "dumb") return 0;

  if (process.stdout?.isTTY) return 1;

  return 0;
}

const colorize = (open: string, close: string) => {
  return (text: unknown): string => {
    if (getColorLevel() === 0) return String(text);
    let str = String(text);
    // Re-open style after newlines to prevent bleed
    const lfIndex = str.indexOf("\n");
    if (lfIndex !== -1) {
      str = str.replaceAll("\n", `${close}\n${open}`);
    }
    return `${open}${str}${close}`;
  };
};

const chalk = {
  red: colorize("\x1b[31m", "\x1b[39m"),
  green: colorize("\x1b[32m", "\x1b[39m"),
  yellow: colorize("\x1b[33m", "\x1b[39m"),
  white: colorize("\x1b[37m", "\x1b[39m"),
  redBright: colorize("\x1b[91m", "\x1b[39m"),
  greenBright: colorize("\x1b[92m", "\x1b[39m"),
};

const FEEDBACK_COLLAPSE_THRESHOLD = 48;
const MAX_TEST_PARAMS_LENGTH = 18;

const RESERVED_KEYS = [
  "Name",
  "Result",
  "Inputs",
  "Reference Outputs",
  "Outputs",
  "pass",
];

function formatTestName(name: string, duration: number) {
  if (duration != null) {
    return `${name} (${duration}ms)`;
  } else {
    return name;
  }
}

function getFormattedStatus(status: string) {
  const s = status.toLowerCase();
  if (s === "pending" || s === "skipped") {
    return chalk.yellow("○ Skipped");
  } else if (s.includes("pass")) {
    return chalk.green("✓ Passed");
  } else if (s.includes("fail")) {
    return chalk.red("✕ Failed");
  } else {
    return status;
  }
}

function getColorParam(status: string) {
  const s = status.toLowerCase();
  if (s === "pending" || s === "skipped") {
    return { color: "yellow" };
  } else if (s.includes("pass")) {
    return { color: "grey" };
  } else if (s.includes("fail")) {
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
        const rawEntry = `${k}: ${rawValue}`;
        const entry =
          rawEntry.length > MAX_TEST_PARAMS_LENGTH
            ? rawEntry.slice(0, MAX_TEST_PARAMS_LENGTH - 3) + "..."
            : rawEntry;
        return entry;
      })
      .join("\n");
  }
  if (value == null) {
    return;
  }
  return String(value);
}

export async function printReporterTable(
  testSuiteName: string,
  results: {
    title: string;
    duration: number;
    status: "pass" | "passed" | "fail" | "failed" | "pending" | "skipped";
  }[],
  testStatus: "pass" | "skip" | "fail" | "passed" | "failed" | "skipped",
  failureMessage?: string
) {
  const rows = [];
  const feedbackKeys = new Set<string>();
  let experimentUrl;
  for (const result of results) {
    const { title, duration, status } = result;
    const titleComponents = title.split(TEST_ID_DELIMITER);
    const testId =
      titleComponents.length > 1 && titleComponents.at(-1) !== undefined
        ? titleComponents.at(-1)
        : undefined;
    const testName =
      testId !== undefined
        ? titleComponents.slice(0, -1).join(TEST_ID_DELIMITER).trim()
        : titleComponents.join(TEST_ID_DELIMITER);
    // Non-LangSmith test
    if (testId === undefined) {
      rows.push([
        {
          Test: formatTestName(testName, duration),
          Status: getFormattedStatus(status),
        },
        getColorParam(status),
      ]);
    } else if (status === "pending" || status === "skipped") {
      // Skipped
      rows.push([
        {
          Test: formatTestName(testName, duration),
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
        console.log(
          "[LANGSMITH]: Failed to read custom evaluation results. Please contact us for help."
        );
        rows.push([
          {
            Test: formatTestName(testName, duration),
            Status: getFormattedStatus(status),
          },
          getColorParam(status),
        ]);
        continue;
      }
      const feedback = fileContent.feedback.reduce(
        (acc: Record<string, ScoreType>, current: SimpleEvaluationResult) => {
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
          Test: formatTestName(testName, duration),
          Inputs: formatValue(fileContent.inputs),
          "Reference Outputs": formatValue(fileContent.referenceOutputs),
          Outputs: formatValue(fileContent.outputs),
          Status: getFormattedStatus(status),
          ...feedback,
        },
        getColorParam(status),
      ]);
    }
  }

  const feedbackKeysTotalLength = [...feedbackKeys].reduce(
    (l, key) => l + key.length,
    0
  );
  const collapseFeedbackColumn =
    feedbackKeysTotalLength > FEEDBACK_COLLAPSE_THRESHOLD;
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
          let coloredKey;
          let coloredScore;
          if (isNaN(deviation)) {
            coloredKey = chalk.white(`${key}:`);
            coloredScore = chalk.white(score);
          } else if (deviation <= -1) {
            coloredKey = chalk.redBright(`${key}:`);
            coloredScore = chalk.redBright(score);
          } else if (deviation < -0.5) {
            coloredKey = chalk.red(`${key}:`);
            coloredScore = chalk.red(score);
          } else if (deviation < 0) {
            coloredKey = chalk.yellow(`${key}:`);
            coloredScore = chalk.yellow(score);
          } else if (deviation === 0) {
            coloredKey = chalk.white(`${key}:`);
            coloredScore = chalk.white(score);
          } else if (deviation <= 0.5) {
            coloredKey = chalk.green(`${key}:`);
            coloredScore = chalk.green(score);
          } else {
            coloredKey = chalk.greenBright(`${key}:`);
            coloredScore = chalk.greenBright(score);
          }
          if (collapseFeedbackColumn) {
            delete row[0][key];
            if (row[0].Feedback === undefined) {
              row[0].Feedback = `${coloredKey} ${coloredScore}`;
            } else {
              row[0].Feedback = `${row[0].Feedback}\n${coloredKey} ${coloredScore}`;
            }
          } else {
            row[0][key] = coloredScore;
          }
        }
      }
    }
  }

  const defaultColumns: {
    name: string;
    alignment?: string;
    maxLen?: number;
    minLen?: number;
  }[] = [
    { name: "Test", alignment: "left", maxLen: 36 },
    { name: "Inputs", alignment: "left", minLen: MAX_TEST_PARAMS_LENGTH },
    {
      name: "Reference Outputs",
      alignment: "left",
      minLen: MAX_TEST_PARAMS_LENGTH,
    },
    { name: "Outputs", alignment: "left", minLen: MAX_TEST_PARAMS_LENGTH },
    { name: "Status", alignment: "left" },
  ];
  if (collapseFeedbackColumn) {
    const feedbackColumnLength = rows.reduce((max, [row]) => {
      const maxFeedbackLineLength =
        row.Feedback?.split("\n").reduce(
          (max: number, feedbackLine: string) => {
            return Math.max(
              max,
              feedbackLine.replace(STRIP_ANSI_REGEX, "").length
            );
          },
          0
        ) ?? 0;
      return Math.max(max, maxFeedbackLineLength);
    }, 0);
    defaultColumns.push({
      name: "Feedback",
      alignment: "left",
      minLen: feedbackColumnLength + 8,
    });
  }
  console.log();
  const table = new Table({
    columns: defaultColumns,
    colorMap: {
      grey: "\x1b[90m",
    },
  });
  for (const row of rows) {
    table.addRow(row[0], row[1]);
  }
  const testStatusColor = testStatus.includes("pass")
    ? chalk.green
    : testStatus.includes("fail")
    ? chalk.red
    : chalk.yellow;
  if (testSuiteName) {
    console.log(testStatusColor(`› ${testSuiteName}`));
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
