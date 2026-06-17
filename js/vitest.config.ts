import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["**/*.test.?(c|m)[jt]s", "**/*.vitesttest.?(c|m)[jt]s"],
    exclude: ["**/*.int.test.?(c|m)[jt]s", "**/*.jesttest.?(c|m)[jt]s", "node_modules"],
    setupFiles: ["dotenv/config"],
    hookTimeout: 30_000,
    testTimeout: 20_000,
  },
});
