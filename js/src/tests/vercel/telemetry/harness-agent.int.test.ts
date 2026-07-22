import { HarnessAgent } from "@ai-sdk/harness/agent";
import { createPi } from "@ai-sdk/harness-pi";
import { createJustBashSandbox } from "@ai-sdk/sandbox-just-bash";
import { tool } from "ai";
import { jest } from "@jest/globals";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import { Client } from "../../../client.js";
import { LangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { toArray, waitUntil } from "../../utils.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";

const PROJECT_NAME = "js-ai-sdk-harness-pi-integration";
const ROOT_RUN_NAME = "AI SDK HarnessAgent with Pi";
const TASK_FILE_NAME = "task-result.txt";
const TASK_FILE_CONTENT = "HarnessAgent and Pi completed this task.";
const TASK_FINAL_RESPONSE = "TASK_COMPLETE";

function expectCompleteToolHistory(inputs: unknown) {
  expect(inputs).toMatchObject({
    messages: [{ role: "user" }, { role: "assistant" }, { role: "tool" }],
  });

  const messages = (inputs as { messages: unknown[] }).messages;
  const toolCalls = (messages[1] as { tool_calls?: Array<{ id?: unknown }> })
    .tool_calls;
  expect(Array.isArray(toolCalls)).toBe(true);
  const toolCallId = toolCalls?.[0]?.id;
  expect(typeof toolCallId).toBe("string");
  expect(messages[2]).toMatchObject({
    role: "tool",
    content: expect.any(String),
    tool_call_id: toolCallId,
    name: "bash",
    artifact: expect.anything(),
  });
  expect(JSON.stringify(messages[2])).toContain(TASK_FILE_CONTENT);
}

function expectToolMessageRun(
  run: {
    name?: string;
    run_type?: string;
    parent_run_id?: string | null;
    inputs?: unknown;
    outputs?: unknown;
  },
  rootRunId: string,
) {
  expect(run).toMatchObject({
    name: "bash",
    run_type: "tool",
    parent_run_id: rootRunId,
    inputs: expect.anything(),
    outputs: { output: expect.any(String) },
  });
  expect(run.inputs).not.toHaveProperty("role");
  expect(run.inputs).not.toHaveProperty("type");
  expect(run.inputs).not.toHaveProperty("toolCallId");
  expect(run.inputs).not.toHaveProperty("toolName");
  expect(JSON.stringify(run.inputs)).toContain(TASK_FILE_NAME);
  expect(JSON.stringify(run.outputs)).toContain(TASK_FILE_CONTENT);
}

test("uploads a real HarnessAgent and Pi trace", async () => {
  const testRunId = randomUUID();
  const currentEnv = Reflect.get(process, "env") as NodeJS.ProcessEnv;
  const anthropicApiKey = currentEnv.ANTHROPIC_API_KEY;
  if (!anthropicApiKey) {
    throw new Error("ANTHROPIC_API_KEY is required for this integration test");
  }

  jest.replaceProperty(process, "env", {
    ...currentEnv,
    TRACE_TO_LANGSMITH: "true",
  });

  const sessionId = `harness-integration-${testRunId}`;
  const callSpy = jest.fn(fetch);
  const client = new Client({
    autoBatchTracing: false,
    fetchImplementation: callSpy,
  });
  const agent = new HarnessAgent({
    harness: createPi({
      auth: { customEnv: { ANTHROPIC_API_KEY: anthropicApiKey } },
      model: "claude-haiku-4-5",
      thinkingLevel: "off",
    }),
    // just-bash 2.14 does not propagate per-command environment variables into
    // nested `bash -c` calls. Seed the known work directory globally until the
    // minimum-release-age constraint allows a version containing that fix.
    sandbox: createJustBashSandbox({
      env: { WORK_DIR: `/home/user/pi-${sessionId}` },
    }),
    telemetry: {
      integrations: [
        LangSmithTelemetry({
          client,
          tracingEnabled: true,
          name: ROOT_RUN_NAME,
          projectName: PROJECT_NAME,
          metadata: {
            integration_test: "ai-sdk-harness-pi",
            test_run_id: testRunId,
          },
          tags: ["integration-test", "ai-sdk-harness", "pi"],
        }),
      ],
    },
  });

  try {
    const session = await agent.createSession({ sessionId });

    try {
      const result = await agent.generate({
        session,
        prompt: [
          `Use the bash tool to create ${TASK_FILE_NAME} in the workspace.`,
          `The file must contain exactly: ${TASK_FILE_CONTENT}`,
          "Print the file contents in the same bash command to verify the write.",
          `After writing the file, reply with exactly ${TASK_FINAL_RESPONSE}.`,
        ].join("\n"),
      });
      expect(result.text.trim()).toBe(TASK_FINAL_RESPONSE);
      expect(JSON.stringify(result.toolResults)).toContain(TASK_FILE_CONTENT);
    } finally {
      await session.destroy();
    }

    await client.awaitPendingTraceBatches();

    await waitUntil(
      async () => {
        const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
        const runs = Object.values(tree.data);
        return (
          runs.some(
            (run) =>
              run.name === ROOT_RUN_NAME &&
              JSON.stringify(run.outputs).includes(TASK_FINAL_RESPONSE),
          ) &&
          runs.some((run) => run.name === "bash" && run.run_type === "tool")
        );
      },
      10_000,
      100,
      "Waiting for HarnessAgent telemetry writes",
    );
    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const outboundRuns = Object.values(tree.data);
    const harnessRoot = outboundRuns.find(
      (run) => run.name === ROOT_RUN_NAME && run.parent_run_id == null,
    );
    if (!harnessRoot?.trace_id) {
      throw new Error("Expected a traced HarnessAgent root run");
    }

    expect(harnessRoot).toMatchObject({
      run_type: "chain",
      outputs: {
        role: "assistant",
        content: [{ type: "text", text: TASK_FINAL_RESPONSE }],
      },
      extra: {
        metadata: {
          ai_sdk_method: "ai.harness",
          integration_test: "ai-sdk-harness-pi",
          test_run_id: testRunId,
        },
      },
    });
    expect(harnessRoot.extra?.metadata).not.toHaveProperty("ls_provider");
    expect(
      outboundRuns.filter((run) => run.parent_run_id === harnessRoot.id),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "pi",
          run_type: "llm",
          extra: expect.objectContaining({
            metadata: expect.objectContaining({
              ls_model_name: "claude-haiku-4-5",
            }),
          }),
          outputs: expect.objectContaining({
            content: expect.arrayContaining([
              expect.objectContaining({
                type: "text",
                text: expect.stringContaining(TASK_FINAL_RESPONSE),
              }),
            ]),
          }),
        }),
      ]),
    );
    const outboundToolRun = outboundRuns.find(
      (run) => run.name === "bash" && run.run_type === "tool",
    );
    if (!outboundToolRun) throw new Error("Expected an outbound Bash tool run");
    expectToolMessageRun(outboundToolRun, harnessRoot.id);
    const finalLlmRun = outboundRuns.find(
      (run) =>
        run.parent_run_id === harnessRoot.id &&
        run.run_type === "llm" &&
        run.extra?.metadata?.step_number === 1,
    );
    expectCompleteToolHistory(finalLlmRun?.inputs);
    expect(finalLlmRun?.extra?.metadata).not.toHaveProperty("ls_provider");

    const readPersistedRuns = () =>
      toArray(
        client.listRuns({
          projectName: PROJECT_NAME,
          traceId: harnessRoot.trace_id,
        }),
      );
    let persistedRuns = await readPersistedRuns();
    await waitUntil(
      async () => {
        persistedRuns = await readPersistedRuns();
        return (
          persistedRuns.some(
            (run) =>
              run.id === harnessRoot.id &&
              run.parent_run_id == null &&
              JSON.stringify(run.outputs).includes(TASK_FINAL_RESPONSE),
          ) &&
          persistedRuns.some(
            (run) =>
              run.parent_run_id === harnessRoot.id &&
              run.run_type === "llm" &&
              run.extra?.metadata?.step_number === 1 &&
              JSON.stringify(run.inputs).includes('"role":"tool"') &&
              JSON.stringify(run.inputs).includes(TASK_FILE_CONTENT),
          ) &&
          persistedRuns.some(
            (run) =>
              run.name === "bash" &&
              run.run_type === "tool" &&
              run.parent_run_id === harnessRoot.id &&
              JSON.stringify(run.inputs).includes(TASK_FILE_NAME) &&
              !JSON.stringify(run.inputs).includes('"role":"user"') &&
              !JSON.stringify(run.inputs).includes('"type":"tool-call"') &&
              JSON.stringify(run.outputs).includes(TASK_FILE_CONTENT),
          )
        );
      },
      30_000,
      500,
      "Waiting for the HarnessAgent with Pi trace",
    );
    expect(
      persistedRuns.filter((run) => run.parent_run_id == null),
    ).toMatchObject([
      {
        name: ROOT_RUN_NAME,
        outputs: {
          role: "assistant",
          content: [{ type: "text", text: TASK_FINAL_RESPONSE }],
        },
      },
    ]);
    const persistedFinalLlmRun = persistedRuns.find(
      (run) =>
        run.parent_run_id === harnessRoot.id &&
        run.run_type === "llm" &&
        run.extra?.metadata?.step_number === 1,
    );
    expectCompleteToolHistory(persistedFinalLlmRun?.inputs);
    expect(persistedFinalLlmRun?.extra?.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
    });
    expect(persistedFinalLlmRun?.extra?.metadata).not.toHaveProperty(
      "ls_provider",
    );
    const persistedToolRun = persistedRuns.find(
      (run) => run.name === "bash" && run.run_type === "tool",
    );
    if (!persistedToolRun)
      throw new Error("Expected a persisted Bash tool run");
    expectToolMessageRun(persistedToolRun, harnessRoot.id);

    const traceUrl = await client.getRunUrl({ run: harnessRoot });
    console.log(`\nReal AI SDK HarnessAgent + Pi trace: ${traceUrl}\n`);
  } finally {
    jest.restoreAllMocks();
  }
}, 60_000);

const SUBAGENT_ROOT_RUN_NAME = "AI SDK HarnessAgent Pi subagent";
const COORDINATOR_ROOT_RUN_NAME = "AI SDK HarnessAgent Pi coordinator";
const DELEGATE_TOOL_NAME = "delegate_to_pi_subagent";
const SUBAGENT_RESULT = "SUBAGENT_RESULT_42";
const COORDINATOR_RESULT = "DELEGATION_COMPLETE";

test("uploads a nested HarnessAgent and Pi coordinator/subagent trace", async () => {
  const testRunId = randomUUID();
  const currentEnv = Reflect.get(process, "env") as NodeJS.ProcessEnv;
  const anthropicApiKey = currentEnv.ANTHROPIC_API_KEY;
  if (!anthropicApiKey) {
    throw new Error("ANTHROPIC_API_KEY is required for this integration test");
  }

  jest.replaceProperty(process, "env", {
    ...currentEnv,
    TRACE_TO_LANGSMITH: "true",
  });

  const callSpy = jest.fn(fetch);
  const client = new Client({
    autoBatchTracing: false,
    fetchImplementation: callSpy,
  });
  const piSettings = {
    auth: { customEnv: { ANTHROPIC_API_KEY: anthropicApiKey } },
    model: "claude-haiku-4-5",
    thinkingLevel: "off" as const,
  };
  const coordinatorSessionId = `harness-coordinator-${testRunId}`;
  let subagentInvocationCount = 0;
  const coordinatorTelemetry = LangSmithTelemetry({
    client,
    tracingEnabled: true,
    name: COORDINATOR_ROOT_RUN_NAME,
    projectName: PROJECT_NAME,
    metadata: {
      integration_test: "ai-sdk-harness-pi-subagent",
      agent_role: "coordinator",
      test_run_id: testRunId,
    },
    tags: ["integration-test", "ai-sdk-harness", "pi", "coordinator"],
  });
  const coordinator = new HarnessAgent({
    id: "pi-coordinator",
    harness: createPi(piSettings),
    sandbox: createJustBashSandbox({
      env: { WORK_DIR: `/home/user/pi-${coordinatorSessionId}` },
    }),
    instructions: [
      `You are a coordinator. You MUST call ${DELEGATE_TOOL_NAME} exactly once.`,
      "Do not solve the delegated task yourself and do not use any other tool.",
      `After the tool returns, reply with exactly ${COORDINATOR_RESULT}.`,
    ].join("\n"),
    tools: {
      [DELEGATE_TOOL_NAME]: tool({
        description:
          "Delegate a self-contained task to an isolated HarnessAgent backed by Pi.",
        inputSchema: z.object({
          task: z
            .string()
            .describe("The complete task for the isolated subagent"),
        }),
        execute: async ({ task }, { abortSignal, toolCallId }) => {
          subagentInvocationCount += 1;
          const subagentSessionId = `harness-subagent-${testRunId}-${toolCallId}`;
          const subagent = new HarnessAgent({
            id: "pi-subagent",
            harness: createPi(piSettings),
            sandbox: createJustBashSandbox({
              env: { WORK_DIR: `/home/user/pi-${subagentSessionId}` },
            }),
            instructions: [
              "You are an isolated subagent.",
              "Complete only the delegated task and do not call tools.",
              `Return exactly ${SUBAGENT_RESULT} as your final response.`,
            ].join("\n"),
            telemetry: {
              integrations: [
                LangSmithTelemetry({
                  client,
                  tracingEnabled: true,
                  name: SUBAGENT_ROOT_RUN_NAME,
                  projectName: PROJECT_NAME,
                  metadata: {
                    integration_test: "ai-sdk-harness-pi-subagent",
                    agent_role: "subagent",
                    parent_tool_call_id: toolCallId,
                    test_run_id: testRunId,
                  },
                  tags: [
                    "integration-test",
                    "ai-sdk-harness",
                    "pi",
                    "subagent",
                  ],
                }),
              ],
            },
          });
          const subagentSession = await subagent.createSession({
            sessionId: subagentSessionId,
            abortSignal,
          });
          try {
            const result = await subagent.generate({
              session: subagentSession,
              prompt: task,
              abortSignal,
            });
            return result.text.trim();
          } finally {
            await subagentSession.destroy();
          }
        },
      }),
    },
    telemetry: { integrations: [coordinatorTelemetry] },
  });

  try {
    const coordinatorSession = await coordinator.createSession({
      sessionId: coordinatorSessionId,
    });
    try {
      const result = await coordinator.generate({
        session: coordinatorSession,
        prompt: [
          `Call ${DELEGATE_TOOL_NAME} with a task that asks the isolated subagent`,
          `to return exactly ${SUBAGENT_RESULT}.`,
          `Then reply with exactly ${COORDINATOR_RESULT}.`,
        ].join(" "),
      });
      expect(result.text.trim()).toBe(COORDINATOR_RESULT);
      expect(JSON.stringify(result.toolResults)).toContain(SUBAGENT_RESULT);
      expect(subagentInvocationCount).toBe(1);
    } finally {
      await coordinatorSession.destroy();
    }

    await client.awaitPendingTraceBatches();
    await waitUntil(
      async () => {
        const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
        const runs = Object.values(tree.data);
        return (
          runs.some(
            (run) =>
              run.name === COORDINATOR_ROOT_RUN_NAME &&
              JSON.stringify(run.outputs).includes(COORDINATOR_RESULT),
          ) &&
          runs.some(
            (run) =>
              run.name === SUBAGENT_ROOT_RUN_NAME &&
              JSON.stringify(run.outputs).includes(SUBAGENT_RESULT),
          ) &&
          runs.some(
            (run) =>
              run.name === DELEGATE_TOOL_NAME &&
              JSON.stringify(run.outputs).includes(SUBAGENT_RESULT),
          )
        );
      },
      10_000,
      100,
      "Waiting for coordinator and subagent telemetry writes",
    );

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const outboundRuns = Object.values(tree.data);
    const coordinatorRoot = outboundRuns.find(
      (run) =>
        run.name === COORDINATOR_ROOT_RUN_NAME && run.parent_run_id == null,
    );
    if (!coordinatorRoot?.trace_id) {
      throw new Error("Expected a traced coordinator root run");
    }

    expect(coordinatorRoot).toMatchObject({
      run_type: "chain",
      outputs: {
        role: "assistant",
        content: [{ type: "text", text: COORDINATOR_RESULT }],
      },
      extra: {
        metadata: {
          ai_sdk_method: "ai.harness",
          agent_role: "coordinator",
          test_run_id: testRunId,
        },
      },
    });
    const delegateRun = outboundRuns.find(
      (run) =>
        run.name === DELEGATE_TOOL_NAME &&
        run.parent_run_id === coordinatorRoot.id,
    );
    if (!delegateRun) throw new Error("Expected a delegate tool run");
    expect(delegateRun).toMatchObject({
      run_type: "tool",
      inputs: { task: expect.stringContaining(SUBAGENT_RESULT) },
      outputs: { output: SUBAGENT_RESULT },
    });
    const subagentRoot = outboundRuns.find(
      (run) =>
        run.name === SUBAGENT_ROOT_RUN_NAME &&
        run.parent_run_id === delegateRun.id,
    );
    if (!subagentRoot?.trace_id) {
      throw new Error("Expected the subagent run beneath the delegate tool");
    }
    const delegateToolCallId = (
      subagentRoot.extra as {
        metadata?: { parent_tool_call_id?: unknown };
      }
    ).metadata?.parent_tool_call_id;
    if (typeof delegateToolCallId !== "string") {
      throw new Error("Expected the subagent tool-call metadata");
    }

    expect(subagentRoot).toMatchObject({
      run_type: "chain",
      outputs: {
        role: "assistant",
        content: [{ type: "text", text: SUBAGENT_RESULT }],
      },
      extra: {
        metadata: {
          ai_sdk_method: "ai.harness",
          agent_role: "subagent",
          parent_tool_call_id: delegateToolCallId,
          test_run_id: testRunId,
        },
      },
    });
    expect(subagentRoot.parent_run_id).toBe(delegateRun.id);
    expect(subagentRoot.trace_id).toBe(coordinatorRoot.trace_id);

    const finalCoordinatorLlm = outboundRuns.find(
      (run) =>
        run.parent_run_id === coordinatorRoot.id &&
        run.run_type === "llm" &&
        run.extra?.metadata?.step_number === 1,
    );
    expect(finalCoordinatorLlm?.inputs).toMatchObject({
      messages: [
        { role: "user" },
        {
          role: "assistant",
          tool_calls: [
            expect.objectContaining({
              id: delegateToolCallId,
              function: expect.objectContaining({ name: DELEGATE_TOOL_NAME }),
            }),
          ],
        },
        {
          role: "tool",
          content: SUBAGENT_RESULT,
          tool_call_id: delegateToolCallId,
          name: DELEGATE_TOOL_NAME,
          artifact: SUBAGENT_RESULT,
        },
      ],
    });

    const coordinatorTraceId = coordinatorRoot.trace_id;
    const readTrace = () =>
      toArray(
        client.listRuns({
          projectName: PROJECT_NAME,
          traceId: coordinatorTraceId,
        }),
      );
    let persistedRuns = await readTrace();
    await waitUntil(
      async () => {
        persistedRuns = await readTrace();
        return (
          persistedRuns.some(
            (run) =>
              run.id === coordinatorRoot.id &&
              JSON.stringify(run.outputs).includes(COORDINATOR_RESULT),
          ) &&
          persistedRuns.some(
            (run) =>
              run.id === delegateRun.id &&
              run.parent_run_id === coordinatorRoot.id &&
              JSON.stringify(run.outputs).includes(SUBAGENT_RESULT),
          ) &&
          persistedRuns.some(
            (run) =>
              run.id === subagentRoot.id &&
              run.parent_run_id === delegateRun.id &&
              run.trace_id === coordinatorTraceId &&
              JSON.stringify(run.outputs).includes(SUBAGENT_RESULT),
          )
        );
      },
      30_000,
      500,
      "Waiting for the persisted nested coordinator/subagent trace",
    );

    const traceUrl = await client.getRunUrl({ run: coordinatorRoot });
    console.log(`\nReal nested Pi coordinator/subagent trace: ${traceUrl}\n`);
  } finally {
    jest.restoreAllMocks();
  }
}, 120_000);
