import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["**/*.vitesteval.?(c|m)[jt]s"],
    reporters: ["./src/vitest/reporter.ts"],
    setupFiles: ["dotenv/config"],
    hookTimeout: 30000,
  },
});
