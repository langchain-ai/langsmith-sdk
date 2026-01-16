import * as fs from "fs";
import * as path from "path";

// This lists all the entrypoints for the library. Each key corresponds to an
// importable path, eg. `import { Foo } from "langsmith/client"`.
// The value is the path to the file in `src/` that exports the entrypoint.
// This is used to generate the `exports` field in package.json.
// Order is not important.
const entrypoints = {
  client: "client",
  run_trees: "run_trees",
  traceable: "traceable",
  evaluation: "evaluation/index",
  schemas: "schemas",
  langchain: "langchain",
  jest: "jest/index",
  "jest/reporter": "jest/reporter",
  vitest: "vitest/index",
  "vitest/reporter": "vitest/reporter",
  wrappers: "wrappers/index",
  anonymizer: "anonymizer/index",
  "wrappers/anthropic": "wrappers/anthropic",
  "wrappers/openai": "wrappers/openai",
  "singletons/traceable": "singletons/traceable",
  "utils/jestlike": "utils/jestlike/index",
  "experimental/otel/setup": "experimental/otel/setup",
  "experimental/otel/exporter": "experimental/otel/exporter",
  "experimental/otel/processor": "experimental/otel/processor",
  "experimental/vercel": "experimental/vercel/index",
};

const defaultEntrypoints = ["vitest/reporter"];

// Easier to have mts files ignored by CJS build
const hasMjs = ["vitest/reporter", "vitest"];

const updateJsonFile = (relativePath, updateFunction) => {
  const contents = fs.readFileSync(relativePath).toString();
  const res = updateFunction(JSON.parse(contents));
  fs.writeFileSync(relativePath, JSON.stringify(res, null, 2) + "\n");
};

const generateFiles = () => {
  const files = [...Object.entries(entrypoints), ["index", "index"]].flatMap(
    ([key, value]) => {
      const nrOfDots = key.split("/").length - 1;
      const relativePath = "../".repeat(nrOfDots) || "./";
      const compiledPath = `${relativePath}dist/${value}.js`;
      const modulePath = hasMjs.includes(key)
        ? `${relativePath}dist/${value}.mjs`
        : compiledPath;
      if (defaultEntrypoints.includes(key)) {
        return [
          [
            `${key}.cjs`,
            `module.exports = require('${relativePath}dist/${value}.cjs').default;`,
          ],
          [`${key}.js`, `export { default } from '${modulePath}'`],
          [`${key}.d.ts`, `export { default } from '${modulePath}'`],
          [`${key}.d.cts`, `export { default } from '${compiledPath}'`],
        ];
      }
      return [
        [
          `${key}.cjs`,
          `module.exports = require('${relativePath}dist/${value}.cjs');`,
        ],
        [`${key}.js`, `export * from '${modulePath}'`],
        [`${key}.d.ts`, `export * from '${modulePath}'`],
        [`${key}.d.cts`, `export * from '${compiledPath}'`],
      ];
    }
  );

  return Object.fromEntries(files);
};

const updateConfig = () => {
  // Update tsconfig.json `typedocOptions.entryPoints` field
  updateJsonFile("./tsconfig.json", (json) => ({
    ...json,
    typedocOptions: {
      ...json.typedocOptions,
      entryPoints: [...Object.keys(entrypoints)].map(
        (key) => `src/${entrypoints[key]}.ts`
      ),
    },
  }));

  const generatedFiles = generateFiles();
  const filenames = Object.keys(generatedFiles);

  // Update package.json `exports` and `files` fields
  updateJsonFile("./package.json", (json) => ({
    ...json,
    exports: Object.assign(
      Object.fromEntries(
        ["index", ...Object.keys(entrypoints)].map((key) => {
          let entryPoint = {
            types: {
              import: `./${key}.d.ts`,
              require: `./${key}.d.cts`,
              default: `./${key}.d.ts`,
            },
            import: `./${key}.js`,
            require: `./${key}.cjs`,
          };

          return [key === "index" ? "." : `./${key}`, entryPoint];
        })
      ),
      {
        "./package.json": "./package.json",
      }
    ),
    files: ["dist/", ...filenames],
  }));

  // Write generated files
  Object.entries(generatedFiles).forEach(([filename, content]) => {
    fs.mkdirSync(path.dirname(filename), {
      recursive: true,
    });
    fs.writeFileSync(filename, content);
  });

  const gitignore = fs.readFileSync("./.gitignore").toString();
  const lines = gitignore.split("\n");
  const startMarker = "## GENERATED create-entrypoints.js";
  const endMarker = "## END GENERATED create-entrypoints.js";
  const startIdx = lines.findIndex((line) => line.includes(startMarker));
  const endIdx = lines.findIndex((line) => line.includes(endMarker));
  const newLines = [
    ...lines.slice(0, startIdx + 1),
    ...filenames.map((fname) => `/${fname}`),
    ...lines.slice(endIdx),
  ];
  fs.writeFileSync("./.gitignore", newLines.join("\n"));
};

const cleanGenerated = () => {
  const filenames = Object.keys(generateFiles());
  filenames.forEach((fname) => {
    try {
      fs.unlinkSync(fname);
    } catch {
      // ignore error
    }
  });
};

const command = process.argv[2];

if (command === "clean") {
  cleanGenerated();
} else {
  updateConfig();
}
