import { defineConfig } from "vite";

export default defineConfig({
  build: {
    // Build as a library to test that imports work
    lib: {
      entry: "src/index.ts",
      formats: ["es"],
      fileName: "index",
    },
    // Don't minify so we can inspect output if needed
    minify: false,
    // Output to dist
    outDir: "dist",
  },
});
