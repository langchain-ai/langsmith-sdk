/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: "ts-jest/presets/default-esm",
  testEnvironment: "node",
  modulePathIgnorePatterns: ["dist/"],
  moduleNameMapper: {
    "^(\\.{1,2}/.*)\\.js$": "$1",
  },
  transform: {
    "^.+\\.m?[tj]sx?$": ["ts-jest", { useESM: true, diagnostics: false }],
  },
  setupFiles: ["dotenv/config"],
  reporters: ["/Users/jacoblee/langchain/langsmith-sdk/js/src/utils/jestlike/reporter.js"],
  testTimeout: 20_000,
};
