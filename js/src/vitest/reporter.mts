/* eslint-disable import/no-extraneous-dependencies */
import { createRequire } from "module";
import { printVitestReporterTable } from "./utils.js";

// Resolve vitest from the current working directory to get the correct version
const require = createRequire(import.meta.url);
let DefaultReporter;
try {
  // Try to resolve from the project's node_modules first
  const vitestPath = require.resolve("vitest/reporters", {
    paths: [process.cwd()],
  });
  const vitestModule = await import(vitestPath);
  DefaultReporter = vitestModule.DefaultReporter;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} catch (error: any) {
  // Fallback to regular import if resolution fails
  const vitestReporters = await import("vitest/reporters");
  DefaultReporter = vitestReporters.DefaultReporter;
}

class LangSmithEvalReporter extends DefaultReporter {
  async onFinished(files: unknown[], errors: unknown[]) {
    super.onFinished(files, errors);
    await printVitestReporterTable(files, this.ctx);
  }
}

export default LangSmithEvalReporter;
