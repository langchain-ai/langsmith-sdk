import { OpenCodeSessionTracer } from "../../experimental/opencode/tracer.js";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { it, expect } from "vitest";
import { mockClient } from "../utils/mock_client.vitest.js";
import { getAssumedTreeFromCalls } from "../utils/tree.js";

async function loadJSONL(fileName: string) {
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  const data = await fs.readFile(path.join(__dirname, fileName), "utf8");
  const lines = data
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
  return lines;
}

it("basic", async () => {
  const { client, callSpy } = mockClient();

  const lines = await loadJSONL("ses_basic.jsonl");
  const tracer = new OpenCodeSessionTracer({
    client,
    tracingEnabled: true,
  });

  for (const [method, ...payload] of lines) {
    if (method === "event") {
      const [input] = payload;
      await tracer.handleEvent(input);
    }

    if (method === "experimental.chat.system.transform") {
      const [input, output] = payload;
      await tracer.handleSystem(input, output);
    }
  }

  const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
  expect(tree).toMatchObject({
    data: {
      "opencode.session:0": {
        name: "opencode.session",
        run_type: "chain",
        extra: {
          metadata: {
            thread_id: expect.any(String),
            ls_integration: "opencode-js",
            ls_agent_type: "root",
            ls_message_format: "anthropic",
          },
        },
        inputs: {
          messages: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: "Read through project files and describe the project for me",
                },
              ],
            },
          ],
        },
        outputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining("LangSmith"),
                }),
              ]),
            }),
          ]),
        },
      },
      "opencode.assistant.turn:1": {
        name: "opencode.assistant.turn",
        run_type: "llm",
        inputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "system",
              content: expect.stringContaining(
                "You are opencode, an interactive CLI tool"
              ),
            }),
            expect.objectContaining({
              role: "user",
              content: [
                expect.objectContaining({
                  type: "text",
                  text: "Read through project files and describe the project for me",
                }),
              ],
            }),
          ]),
        },
        outputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "thinking",
                  thinking: expect.stringContaining("project"),
                }),
                expect.objectContaining({ type: "tool_use", name: "read" }),
                expect.objectContaining({
                  type: "tool_use",
                  name: "glob",
                  input: { pattern: "**/*.ts" },
                }),
              ]),
            }),
          ]),
        },
      },
      "read:2": {
        name: "read",
        run_type: "tool",
        inputs: { filePath: expect.stringContaining("ls-opencode") },
        outputs: {
          output: expect.stringContaining("<type>directory</type>"),
        },
      },
      "read:3": {
        name: "read",
        run_type: "tool",
        inputs: {
          filePath: expect.stringContaining("package.json"),
        },
        outputs: {
          output: expect.stringContaining('"name": "ls-opencode"'),
        },
      },
      "glob:4": {
        name: "glob",
        run_type: "tool",
        inputs: { pattern: "**/*.ts" },
        outputs: { output: "No files found" },
      },
      "opencode.assistant.turn:5": {
        name: "opencode.assistant.turn",
        run_type: "llm",
        inputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "system",
              content: expect.stringContaining(
                "You are opencode, an interactive CLI tool"
              ),
            }),
            expect.objectContaining({
              role: "user",
              content: [
                expect.objectContaining({
                  type: "text",
                  text: "Read through project files and describe the project for me",
                }),
              ],
            }),
          ]),
        },
        outputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "thinking",
                  thinking: expect.stringContaining("TypeScript"),
                }),
                expect.objectContaining({
                  type: "tool_use",
                  name: "read",
                  input: {
                    filePath: expect.stringContaining("ls-opencode/src"),
                  },
                }),
                expect.objectContaining({
                  type: "tool_use",
                  name: "read",
                  input: {
                    filePath: expect.stringContaining("README.md"),
                  },
                }),
                expect.objectContaining({
                  type: "tool_use",
                  name: "glob",
                  input: {},
                }),
              ]),
            }),
          ]),
        },
      },
      "read:6": {
        name: "read",
        run_type: "tool",
        inputs: { filePath: expect.stringContaining("ls-opencode/src") },
        outputs: {
          output: expect.stringContaining("index.mts"),
        },
      },
      "read:7": {
        name: "read",
        run_type: "tool",
        inputs: { filePath: expect.stringContaining("README.md") },
        outputs: {
          output: expect.stringContaining("bun install"),
        },
      },
      "glob:8": {
        name: "glob",
        run_type: "tool",
        inputs: {},
        outputs: {},
        error: expect.stringContaining(
          "Invalid input: expected string, received undefined"
        ),
      },
      "glob:9": {
        name: "glob",
        run_type: "tool",
        inputs: {},
        outputs: {},
        error: expect.stringContaining(
          "Invalid input: expected string, received undefined"
        ),
      },
      "opencode.assistant.turn:10": {
        name: "opencode.assistant.turn",
        run_type: "llm",
        inputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "system",
              content: expect.stringContaining(
                "You are opencode, an interactive CLI tool"
              ),
            }),
            expect.objectContaining({
              role: "user",
              content: [
                expect.objectContaining({
                  type: "text",
                  text: "Read through project files and describe the project for me",
                }),
              ],
            }),
          ]),
        },
        outputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "tool_use",
                  name: "read",
                  input: {
                    filePath: expect.stringContaining("index.mts"),
                  },
                }),
                expect.objectContaining({
                  type: "tool_use",
                  name: "read",
                  input: {
                    filePath: expect.stringContaining("opencode.json"),
                  },
                }),
              ]),
            }),
          ]),
        },
      },
      "read:11": {
        name: "read",
        run_type: "tool",
        inputs: { filePath: expect.stringContaining("index.mts") },
        outputs: {
          output: expect.stringContaining("(End of file - total 0 lines)"),
        },
      },
      "read:12": {
        name: "read",
        run_type: "tool",
        inputs: { filePath: expect.stringContaining("opencode.json") },
        outputs: {
          output: expect.stringContaining("opencode.ai/config.json"),
        },
      },
      "opencode.assistant.turn:13": {
        name: "opencode.assistant.turn",
        run_type: "llm",
        inputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "system",
              content: expect.stringContaining(
                "You are opencode, an interactive CLI tool"
              ),
            }),
            expect.objectContaining({
              role: "user",
              content: [
                expect.objectContaining({
                  type: "text",
                  text: "Read through project files and describe the project for me",
                }),
              ],
            }),
          ]),
        },
        outputs: {
          messages: [
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining("LangSmith"),
                }),
              ]),
            }),
          ],
        },
      },
    },
  });
});

it("editing", async () => {
  const { client, callSpy } = mockClient();
  const lines = await loadJSONL("ses_editing.jsonl");
  const tracer = new OpenCodeSessionTracer({
    client,
    project_name: "david-opencode",
    name: "opencode.session.editing",
    tracingEnabled: true,
  });

  for (const [method, ...payload] of lines) {
    if (method === "event") {
      const [input] = payload;
      await tracer.handleEvent(input);
    }

    if (method === "experimental.chat.system.transform") {
      const [input, output] = payload;
      await tracer.handleSystem(input, output);
    }
  }

  const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
  expect(tree).toMatchObject({
    data: {
      "opencode.session.editing:0": {
        name: "opencode.session.editing",
        run_type: "chain",
        inputs: {
          messages: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: "Write a sample NodeJS app printing cowsay",
                },
              ],
            },
          ],
        },
        outputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining("cowsay"),
                }),
              ]),
            }),
          ]),
        },
      },
      "glob:2": {
        name: "glob",
        run_type: "tool",
        inputs: { pattern: "*" },
        outputs: {
          output: expect.stringContaining("/Users/duongtat/Work/ls-opencode"),
        },
      },
      "write:4": {
        name: "write",
        run_type: "tool",
        inputs: {
          filePath: expect.stringContaining("cowsay.ts"),
          content: expect.stringContaining("import cowsay from"),
        },
        outputs: {
          output: "Wrote file successfully.",
        },
      },
      "bash:6": {
        name: "bash",
        run_type: "tool",
        inputs: {
          command: expect.stringContaining("bun add cowsay"),
        },
        outputs: {
          output: expect.stringContaining("installed cowsay@"),
        },
      },
    },
  });
});

it("images", async () => {
  const { client, callSpy } = mockClient();
  const lines = await loadJSONL("ses_images.jsonl");
  const tracer = new OpenCodeSessionTracer({
    client,
    project_name: "david-opencode",
    name: "opencode.session.images",
    tracingEnabled: true,
  });

  for (const [method, ...payload] of lines) {
    if (method === "event") {
      const [input] = payload;
      await tracer.handleEvent(input);
    }

    if (method === "experimental.chat.system.transform") {
      const [input, output] = payload;
      await tracer.handleSystem(input, output);
    }
  }

  const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
  expect(tree).toMatchObject({
    data: {
      "opencode.session.images:0": {
        name: "opencode.session.images",
        run_type: "chain",
        inputs: {
          messages: [
            {
              role: "user",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: "[Image 1] What's this describing?",
                }),
                expect.objectContaining({
                  type: "file",
                  id: "clipboard",
                  mime_type: "image/png",
                }),
              ]),
            },
          ],
        },
        outputs: {
          messages: [
            {
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining("I cannot view images"),
                }),
              ]),
            },
          ],
        },
      },
      "opencode.assistant.turn:1": {
        name: "opencode.assistant.turn",
        run_type: "llm",
        inputs: {
          messages: expect.arrayContaining([
            expect.objectContaining({
              role: "user",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "file",
                  id: "clipboard",
                  mime_type: "image/png",
                }),
              ]),
            }),
          ]),
        },
        outputs: {
          messages: [
            expect.objectContaining({
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining(
                    "Please describe what's in the image"
                  ),
                }),
              ]),
            }),
          ],
        },
      },
    },
  });
});

it("subagents", async () => {
  const { client, callSpy } = mockClient();
  const lines = await loadJSONL("ses_subagents.jsonl");
  const tracer = new OpenCodeSessionTracer({
    client,
    project_name: "david-opencode",
    name: "opencode.session.subagents",
    tracingEnabled: true,
  });

  for (const [method, ...payload] of lines) {
    if (method === "event") {
      const [input] = payload;
      await tracer.handleEvent(input);
    }

    if (method === "experimental.chat.system.transform") {
      const [input, output] = payload;
      await tracer.handleSystem(input, output);
    }
  }

  const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
  expect(tree).toMatchObject({
    data: {
      "opencode.session.subagents:0": {
        name: "opencode.session.subagents",
        run_type: "chain",
        inputs: {
          messages: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: "Call a general subagent that will get the latest time and tell a joke using that time",
                },
              ],
            },
          ],
        },
        outputs: {
          messages: [
            {
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({ type: "tool_use", name: "task" }),
              ]),
            },
            {
              role: "tool",
              name: "task",
              content: expect.stringContaining("It's **12:52 AM**."),
            },
            {
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining(
                    "The current time is **12:52 AM**."
                  ),
                }),
              ]),
            },
          ],
        },
      },
      "opencode.session.subagents:2": {
        name: "opencode.session.subagents",
        run_type: "chain",
        inputs: {
          messages: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: expect.stringContaining("Please get the current time"),
                },
              ],
            },
          ],
        },
        outputs: {
          messages: [
            {
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "tool_use",
                  name: "bash",
                }),
              ]),
            },
            {
              role: "tool",
              name: "bash",
              content: expect.stringContaining("12:52 AM"),
            },
            {
              role: "assistant",
              content: expect.arrayContaining([
                expect.objectContaining({
                  type: "text",
                  text: expect.stringContaining("It's **12:52 AM**."),
                }),
              ]),
            },
          ],
        },
      },
      "bash:4": {
        name: "bash",
        run_type: "tool",
        inputs: { command: 'date +"%I:%M %p"' },
        outputs: { output: expect.stringContaining("12:52 AM") },
      },
    },
  });
});
