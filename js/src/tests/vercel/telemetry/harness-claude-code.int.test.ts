import { HarnessAgent } from "@ai-sdk/harness/agent";
import { createClaudeCode } from "@ai-sdk/harness-claude-code";
import { createVercelSandbox } from "@ai-sdk/sandbox-vercel";
import { jest } from "@jest/globals";
import { randomUUID } from "node:crypto";
import { Client } from "../../../client.js";
import { LangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { toArray, waitUntil } from "../../utils.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";

const PROJECT_NAME = "js-ai-sdk-harness-claude-code-integration";
const ROOT_RUN_NAME = "AI SDK HarnessAgent with Claude Code";
const BRIDGE_PORT = 4000;

function hasNonEmptyTextOutput(outputs: unknown): boolean {
  if (outputs == null || typeof outputs !== "object") return false;
  const content = (outputs as { content?: unknown }).content;
  return (
    Array.isArray(content) &&
    content.some(
      (part) =>
        part != null &&
        typeof part === "object" &&
        (part as { type?: unknown }).type === "text" &&
        typeof (part as { text?: unknown }).text === "string" &&
        (part as { text: string }).text.trim().length > 0,
    )
  );
}

function expectCompletedLlmRun(run: {
  outputs?: unknown;
  end_time?: string | number;
  extra?: { metadata?: Record<string, any> };
}) {
  expect(run).toMatchObject({
    end_time: expect.anything(),
    extra: {
      metadata: {
        usage_metadata: {
          input_tokens: expect.any(Number),
          output_tokens: expect.any(Number),
          total_tokens: expect.any(Number),
        },
      },
    },
  });
  expect(hasNonEmptyTextOutput(run.outputs)).toBe(true);
  expect(
    run.extra?.metadata?.usage_metadata?.total_tokens as number,
  ).toBeGreaterThan(0);
}

// Requires a Vercel key
test.skip(
  "uploads a real HarnessAgent and Claude Code trace",
  async () => {
    const testRunId = randomUUID();
    const currentEnv = Reflect.get(process, "env") as NodeJS.ProcessEnv;
    const anthropicApiKey = currentEnv.ANTHROPIC_API_KEY;
    if (!anthropicApiKey) {
      throw new Error(
        "ANTHROPIC_API_KEY is required for this integration test",
      );
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
    const agent = new HarnessAgent({
      harness: createClaudeCode({
        auth: { anthropic: { apiKey: anthropicApiKey } },
        model: "claude-haiku-4-5",
        maxTurns: 1,
        port: BRIDGE_PORT,
      }),
      sandbox: createVercelSandbox({
        runtime: "node24",
        ports: [BRIDGE_PORT],
        timeout: 10 * 60 * 1000,
      }),
      telemetry: {
        integrations: [
          LangSmithTelemetry({
            client,
            tracingEnabled: true,
            name: ROOT_RUN_NAME,
            projectName: PROJECT_NAME,
            metadata: {
              integration_test: "ai-sdk-harness-claude-code",
              test_run_id: testRunId,
            },
            tags: ["integration-test", "ai-sdk-harness", "claude-code"],
          }),
        ],
      },
    });

    try {
      const session = await agent.createSession({
        sessionId: `harness-claude-code-${testRunId}`,
      });
      try {
        const result = await agent.generate({
          session,
          prompt: "Reply with one short sentence about observability.",
        });
        expect(result.text.trim().length).toBeGreaterThan(0);
      } finally {
        await session.destroy();
      }

      await client.awaitPendingTraceBatches();
      await waitUntil(
        async () => {
          const tree = await getAssumedTreeFromCalls(
            callSpy.mock.calls,
            client,
          );
          const runs = Object.values(tree.data);
          const root = runs.find(
            (run) => run.name === ROOT_RUN_NAME && run.parent_run_id == null,
          );
          return (
            root != null &&
            runs.some(
              (run) =>
                run.parent_run_id === root.id &&
                run.run_type === "llm" &&
                run.end_time != null &&
                hasNonEmptyTextOutput(run.outputs) &&
                typeof run.extra?.metadata?.usage_metadata?.total_tokens ===
                  "number",
            )
          );
        },
        30_000,
        250,
        "Waiting for completed Claude Code telemetry writes",
      );

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const outboundRuns = Object.values(tree.data);
      const root = outboundRuns.find(
        (run) => run.name === ROOT_RUN_NAME && run.parent_run_id == null,
      );
      if (!root?.trace_id) {
        throw new Error("Expected a traced Claude Code root run");
      }
      expect(root).toMatchObject({
        run_type: "chain",
        end_time: expect.anything(),
        extra: {
          metadata: {
            ai_sdk_method: "ai.harness",
            integration_test: "ai-sdk-harness-claude-code",
            test_run_id: testRunId,
          },
        },
      });
      expect(root.extra?.metadata).not.toHaveProperty("usage_metadata");

      const llmRuns = outboundRuns.filter(
        (run) => run.parent_run_id === root.id && run.run_type === "llm",
      );
      expect(llmRuns).toHaveLength(1);
      const [llmRun] = llmRuns;
      expectCompletedLlmRun(llmRun);

      const readTrace = () =>
        toArray(
          client.listRuns({
            projectName: PROJECT_NAME,
            traceId: root.trace_id,
          }),
        );
      let persistedRuns = await readTrace();
      await waitUntil(
        async () => {
          persistedRuns = await readTrace();
          const persistedLlm = persistedRuns.find(
            (run) => run.id === llmRun.id,
          );
          return (
            persistedLlm != null &&
            persistedLlm.end_time != null &&
            hasNonEmptyTextOutput(persistedLlm.outputs) &&
            typeof persistedLlm.extra?.metadata?.usage_metadata
              ?.total_tokens === "number"
          );
        },
        30_000,
        500,
        "Waiting for the persisted Claude Code trace",
      );

      const persistedRoot = persistedRuns.find((run) => run.id === root.id);
      const persistedLlm = persistedRuns.find((run) => run.id === llmRun.id);
      expect(persistedRoot).toMatchObject({ end_time: expect.anything() });
      expect(persistedRoot?.extra?.metadata).not.toHaveProperty(
        "usage_metadata",
      );
      if (!persistedLlm)
        throw new Error("Expected a persisted Claude Code LLM run");
      expectCompletedLlmRun(persistedLlm);

      const traceUrl = await client.getRunUrl({ run: root });
      console.log(
        `\nReal AI SDK HarnessAgent + Claude Code trace: ${traceUrl}\n`,
      );
    } finally {
      jest.restoreAllMocks();
    }
  },
  15 * 60_000,
);
