/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: "ts-jest/presets/default-esm",
  testEnvironment: "node",
  modulePathIgnorePatterns: ["dist/"],
  testPathIgnorePatterns: [
    "\\.vitesttest\\.",
    "\\.vitesteval\\.",
    "cache.*\\.int\\.test\\.ts$",
    "rate_limit.*\\.int\\.test\\.ts$",
    "ai_sdk_evaluate\\.int\\.test\\.ts$",
  ],
  moduleNameMapper: {
    "^(\\.{1,2}/.*)\\.js$": "$1",
  },
  transform: {
    "^.+\\.m?[tj]sx?$": [
      "ts-jest",
      { useESM: true, diagnostics: false, isolatedModules: true },
    ],
  },
  setupFiles: ["dotenv/config"],
  testTimeout: 20_000,
  maxConcurrency: 5,
  // Retry flaky integration tests up to 3 times
  retryTimes: 3,
  retryImmediately: false,
};
