import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["**/*.vitesttest.?(c|m)[jt]s"],
    setupFiles: ["dotenv/config"],
    hookTimeout: 30000,
  },
});
