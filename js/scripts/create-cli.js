import * as fs from "fs";
import * as path from "path";

let dirname = new URL(".", import.meta.url).pathname;
// If on Windows, remove the leading slash
if (process.platform === "win32" && dirname.startsWith("/")) {
  dirname = dirname.slice(1);
}

const mainPath = path.join(dirname, "../dist/cli/main.cjs");
const mainContents = fs.readFileSync(mainPath).toString();
const shebang = "#!/usr/bin/env node\n";
const newContents = shebang + mainContents;
// Update file contents
fs.writeFileSync(mainPath, newContents);
// Make the file executable
fs.chmodSync(mainPath, "755");

// Copy the docker compose files over
const yamlFiles = fs.readdirSync(path.join(dirname, "../src/cli"));
for (const yamlFile of yamlFiles) {
  const srcPath = path.join(dirname, "../src/cli", yamlFile);
  const destPath = path.join(dirname, "../dist/cli", yamlFile);
  fs.copyFileSync(srcPath, destPath);
}
