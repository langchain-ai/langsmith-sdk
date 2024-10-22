import type { ReadableSpan, SpanExporter } from "@opentelemetry/sdk-trace-base";
import type { ExportResult } from "@opentelemetry/core";
import type { CoreAssistantMessage, CoreMessage, ToolCallPart } from "ai";
import type { AISDKSpan } from "./exporter.types.js";
import { Client } from "../../index.js";
import { KVMap, RunCreate } from "../../schemas.js";
import { v5 as uuid5 } from "uuid";

// eslint-disable-next-line @typescript-eslint/ban-types
type AnyString = string & {};

type LangChainMessageFields = {
  content:
    | string
    | Array<
        | { type: "text"; text: string }
        | {
            type: "image_url";
            image_url:
              | string
              | {
                  url: string;
                  detail?: "auto" | "low" | "high" | AnyString;
                };
          }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        | (Record<string, any> & { type?: "text" | "image_url" | string })
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        | (Record<string, any> & { type?: never })
      >;
  name?: string;
  id?: string;
  additional_kwargs?: {
    tool_calls?: {
      id: string;
      function: { arguments: string; name: string };
      type: "function";
      index?: number;
    }[];
    [key: string]: unknown;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  response_metadata?: Record<string, any>;
};
type LangChainLikeMessage = { type: string; data: LangChainMessageFields };

// Attempt to convert CoreMessage to a LangChain-compatible format
// which allows us to render messages more nicely in LangSmith
function convertCoreToSmith(
  message: CoreMessage
):
  | LangChainLikeMessage
  | CoreMessage
  | Array<LangChainLikeMessage | CoreMessage> {
  if (message.role === "assistant") {
    const data: LangChainMessageFields = { content: message.content };

    if (Array.isArray(message.content)) {
      data.content = message.content.map((part) => {
        if (part.type === "text") {
          return {
            type: "text",
            text: part.text,
            ...part.experimental_providerMetadata,
          };
        }

        if (part.type === "tool-call") {
          return {
            type: "tool_use",
            name: part.toolName,
            id: part.toolCallId,
            input: part.args,
            ...part.experimental_providerMetadata,
          };
        }

        return part;
      });

      const toolCalls = message.content.filter(
        (part): part is ToolCallPart => part.type === "tool-call"
      );

      if (toolCalls.length > 0) {
        data.additional_kwargs ??= {};
        data.additional_kwargs.tool_calls = toolCalls.map((part) => {
          return {
            id: part.toolCallId,
            type: "function",
            function: {
              name: part.toolName,
              id: part.toolCallId,
              arguments: JSON.stringify(part.args),
            },
          };
        });
      }
    }

    return { type: "ai", data };
  }

  if (message.role === "user") {
    const data: LangChainMessageFields = { content: message.content };

    if (Array.isArray(message.content)) {
      data.content = message.content.map((part) => {
        if (part.type === "text") {
          return {
            type: "text",
            text: part.text,
            ...part.experimental_providerMetadata,
          };
        }

        if (part.type === "image") {
          return {
            type: "image_url",
            image_url: part.image,
            ...part.experimental_providerMetadata,
          };
        }

        return part;
      });
    }

    return { type: "human", data };
  }

  if (message.role === "system") {
    return { type: "system", data: { content: message.content } };
  }

  if (message.role === "tool") {
    const res = message.content.map((toolCall) => {
      return {
        type: "tool",
        data: {
          content: JSON.stringify(toolCall.result),
          name: toolCall.toolName,
          tool_call_id: toolCall.toolCallId,
        },
      };
    });
    if (res.length === 1) return res[0];
    return res;
  }

  return message;
}

const tryJson = (
  str:
    | string
    | number
    | boolean
    | Array<null | undefined | string>
    | Array<null | undefined | number>
    | Array<null | undefined | boolean>
    | undefined
) => {
  try {
    if (!str) return str;
    if (typeof str !== "string") return str;
    return JSON.parse(str);
  } catch {
    return str;
  }
};

function stripNonAlphanumeric(input: string) {
  return input.replace(/[-:.]/g, "");
}

function convertToDottedOrderFormat(
  [seconds, nanoseconds]: [seconds: number, nanoseconds: number],
  runId: string,
  executionOrder: number
) {
  // Date only has millisecond precision, so we use the microseconds to break
  // possible ties, avoiding incorrect run order
  const ms = Number(String(nanoseconds).slice(0, 3));
  const ns = String(Number(String(nanoseconds).slice(3, 6)) + executionOrder)
    .padStart(3, "0")
    .slice(0, 3);

  return (
    stripNonAlphanumeric(
      `${new Date(seconds * 1000 + ms).toISOString().slice(0, -1)}${ns}Z`
    ) + runId
  );
}

function convertToTimestamp([seconds, nanoseconds]: [
  seconds: number,
  nanoseconds: number
]) {
  const ms = String(nanoseconds).slice(0, 3);
  return Number(String(seconds) + ms);
}

const RUN_ID_NAMESPACE = "5c718b20-9078-11ef-9a3d-325096b39f47";

interface RunTask {
  id: string;
  parentId: string | undefined;
  startTime: [seconds: number, nanoseconds: number];
  run: RunCreate;
  sent: boolean;
  executionOrder: number;
}

export class LangSmithAISDKExporter implements SpanExporter {
  private client: Client;
  private traceByMap: Record<
    string,
    {
      childMap: Record<string, RunTask[]>;
      nodeMap: Record<string, RunTask>;
      relativeExecutionOrder: Record<string, number>;
      userTraceId?: string;
    }
  > = {};

  constructor(args?: { client?: Client }) {
    this.client = args?.client ?? new Client();
  }

  /** @internal */
  protected getRunCreate(span: AISDKSpan): RunCreate | undefined {
    const runId = uuid5(span.spanContext().spanId, RUN_ID_NAMESPACE);
    const parentRunId = span.parentSpanId
      ? uuid5(span.parentSpanId, RUN_ID_NAMESPACE)
      : undefined;

    const asRunCreate = (rawConfig: RunCreate) => {
      const aiMetadata = Object.keys(span.attributes)
        .filter(
          (key) =>
            key.startsWith("ai.telemetry.metadata.") &&
            key !== "ai.telemetry.metadata.langsmithRunId"
        )
        .reduce((acc, key) => {
          acc[key.slice("ai.telemetry.metadata.".length)] =
            span.attributes[key as keyof typeof span.attributes];

          return acc;
        }, {} as Record<string, unknown>);

      if (
        ("ai.telemetry.functionId" in span.attributes &&
          span.attributes["ai.telemetry.functionId"]) ||
        ("resource.name" in span.attributes && span.attributes["resource.name"])
      ) {
        aiMetadata["functionId"] =
          span.attributes["ai.telemetry.functionId"] ||
          span.attributes["resource.name"];
      }

      const config: RunCreate = {
        ...rawConfig,
        id: runId,
        parent_run_id: parentRunId,
        extra: {
          ...rawConfig.extra,
          metadata: {
            ...rawConfig.extra?.metadata,
            ...aiMetadata,
            "ai.operationId": span.attributes["ai.operationId"],
          },
        },
        start_time: convertToTimestamp(span.startTime),
        end_time: convertToTimestamp(span.endTime),
      };

      return config;
    };

    switch (span.name) {
      case "ai.generateText.doGenerate":
      case "ai.generateText":
      case "ai.streamText.doStream":
      case "ai.streamText": {
        const inputs = ((): KVMap => {
          if ("ai.prompt.messages" in span.attributes) {
            return {
              messages: tryJson(span.attributes["ai.prompt.messages"]).flatMap(
                (i: CoreMessage) => convertCoreToSmith(i)
              ),
            };
          }

          if ("ai.prompt" in span.attributes) {
            const input = tryJson(span.attributes["ai.prompt"]);

            if (
              typeof input === "object" &&
              input != null &&
              "messages" in input &&
              Array.isArray(input.messages)
            ) {
              return {
                messages: input.messages.flatMap((i: CoreMessage) =>
                  convertCoreToSmith(i)
                ),
              };
            }

            return { input };
          }

          return {};
        })();

        const outputs = ((): KVMap | undefined => {
          let result: KVMap | undefined = undefined;
          if (span.attributes["ai.response.toolCalls"]) {
            result = {
              llm_output: convertCoreToSmith({
                role: "assistant",
                content: tryJson(span.attributes["ai.response.toolCalls"]),
              } satisfies CoreAssistantMessage),
            };
          } else if (span.attributes["ai.response.text"]) {
            result = {
              llm_output: convertCoreToSmith({
                role: "assistant",
                content: span.attributes["ai.response.text"],
              }),
            };
          }

          if (span.attributes["ai.usage.completionTokens"]) {
            result ??= {};
            result.llm_output ??= {};
            result.llm_output.token_usage ??= {};
            result.llm_output.token_usage["completion_tokens"] =
              span.attributes["ai.usage.completionTokens"];
          }

          if (span.attributes["ai.usage.promptTokens"]) {
            result ??= {};
            result.llm_output ??= {};
            result.llm_output.token_usage ??= {};
            result.llm_output.token_usage["prompt_tokens"] =
              span.attributes["ai.usage.promptTokens"];
          }

          return result;
        })();

        // TODO: add first_token_time
        return asRunCreate({
          run_type: "llm",
          name: span.attributes["ai.model.provider"],
          inputs,
          outputs,
          extra: {
            batch_size: 1,
            metadata: {
              ls_provider: span.attributes["ai.model.provider"]
                .split(".")
                .at(0),
              ls_model_type: span.attributes["ai.model.provider"]
                .split(".")
                .at(1),
              ls_model_name: span.attributes["ai.model.id"],
            },
          },
        });
        break;
      }

      case "ai.toolCall": {
        const args = tryJson(span.attributes["ai.toolCall.args"]);
        let inputs: KVMap = { args };

        if (typeof args === "object" && args != null) {
          inputs = args;
        }

        const output = tryJson(span.attributes["ai.toolCall.result"]);
        let outputs: KVMap = { output };

        if (typeof output === "object" && output != null) {
          outputs = output;
        }

        return asRunCreate({
          run_type: "tool",
          name: span.attributes["ai.toolCall.name"],
          inputs,
          outputs,
        });
      }

      case "ai.streamObject":
      case "ai.streamObject.doStream":
      case "ai.generateObject":
      case "ai.generateObject.doGenerate": {
        const inputs = ((): KVMap => {
          if ("ai.prompt.messages" in span.attributes) {
            return {
              messages: tryJson(span.attributes["ai.prompt.messages"]).flatMap(
                (i: CoreMessage) => convertCoreToSmith(i)
              ),
            };
          }

          if ("ai.prompt" in span.attributes) {
            return { input: tryJson(span.attributes["ai.prompt"]) };
          }

          return {};
        })();

        const outputs = ((): KVMap | undefined => {
          let result: KVMap | undefined = undefined;

          if (span.attributes["ai.response.object"]) {
            result = {
              output: tryJson(span.attributes["ai.response.object"]),
            };
          }

          if (span.attributes["ai.usage.completionTokens"]) {
            result ??= {};
            result.llm_output ??= {};
            result.llm_output.token_usage ??= {};
            result.llm_output.token_usage["completion_tokens"] =
              span.attributes["ai.usage.completionTokens"];
          }

          if (span.attributes["ai.usage.promptTokens"]) {
            result ??= {};
            result.llm_output ??= {};
            result.llm_output.token_usage ??= {};
            result.llm_output.token_usage["prompt_tokens"] =
              +span.attributes["ai.usage.promptTokens"];
          }

          return result;
        })();

        return asRunCreate({
          run_type: "llm",
          name: span.attributes["ai.model.provider"],
          inputs,
          outputs,
          extra: {
            batch_size: 1,
            metadata: {
              ls_provider: span.attributes["ai.model.provider"]
                .split(".")
                .at(0),
              ls_model_type: span.attributes["ai.model.provider"]
                .split(".")
                .at(1),
              ls_model_name: span.attributes["ai.model.id"],
            },
          },
        });
      }

      case "ai.embed":
      case "ai.embed.doEmbed":
      case "ai.embedMany":
      case "ai.embedMany.doEmbed":
      default:
        console.warn(`Span "${span.name}" is currently unsupported.`);
        return undefined;
    }
  }

  export(
    spans: ReadableSpan[],
    resultCallback: (result: ExportResult) => void
  ): void {
    for (const span of spans) {
      const { traceId, spanId } = span.spanContext();
      const parentId = span.parentSpanId ?? undefined;
      this.traceByMap[traceId] ??= {
        childMap: {},
        nodeMap: {},
        relativeExecutionOrder: {},
      };

      const runId = uuid5(spanId, RUN_ID_NAMESPACE);
      const parentRunId = parentId
        ? uuid5(parentId, RUN_ID_NAMESPACE)
        : undefined;

      const traceMap = this.traceByMap[traceId];

      const aiSpan = span as AISDKSpan;
      const run = this.getRunCreate(aiSpan);
      if (!run) continue;

      traceMap.relativeExecutionOrder[parentRunId ?? "$"] ??= -1;
      traceMap.relativeExecutionOrder[parentRunId ?? "$"] += 1;

      traceMap.nodeMap[runId] ??= {
        id: runId,
        parentId: parentRunId,
        startTime: span.startTime,
        run,
        sent: false,
        executionOrder: traceMap.relativeExecutionOrder[parentRunId ?? "$"],
      };

      traceMap.childMap[parentRunId ?? "$"] ??= [];
      traceMap.childMap[parentRunId ?? "$"].push(traceMap.nodeMap[runId]);

      if (
        "ai.telemetry.metadata.langsmithRunId" in aiSpan.attributes &&
        typeof aiSpan.attributes["ai.telemetry.metadata.langsmithRunId"] ===
          "string" &&
        aiSpan.attributes["ai.telemetry.metadata.langsmithRunId"]
      ) {
        traceMap.userTraceId =
          aiSpan.attributes["ai.telemetry.metadata.langsmithRunId"];
      }
    }

    // collect all subgraphs
    const sampled: [
      {
        dotted_order: string;
        id: string;
        trace_id: string;
        parent_run_id: string | undefined;
      },
      RunCreate
    ][] = [];

    for (const traceId of Object.keys(this.traceByMap)) {
      type QueueItem = { item: RunTask; dottedOrder: string; traceId: string };
      const traceMap = this.traceByMap[traceId];

      const queue: QueueItem[] =
        traceMap.childMap["$"]?.map((item) => ({
          item,
          dottedOrder: convertToDottedOrderFormat(
            item.startTime,
            item.id,
            item.executionOrder
          ),
          traceId: item.id,
        })) ?? [];

      const seen = new Set<string>();
      while (queue.length) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        const task = queue.shift()!;
        if (seen.has(task.item.id)) continue;

        if (!task.item.sent) {
          let ident = {
            id: task.item.id,
            parent_run_id: task.item.parentId,
            dotted_order: task.dottedOrder,
            trace_id: task.traceId,
          };

          if (traceMap.userTraceId) {
            ident = {
              id: ident.id === ident.trace_id ? traceMap.userTraceId : ident.id,
              parent_run_id:
                ident.parent_run_id === ident.trace_id
                  ? traceMap.userTraceId
                  : ident.parent_run_id,
              dotted_order: ident.dotted_order.replace(
                ident.trace_id,
                traceMap.userTraceId
              ),
              trace_id: traceMap.userTraceId,
            };
          }

          sampled.push([ident, task.item.run]);
          task.item.sent = true;
        }

        const children = traceMap.childMap[task.item.id] ?? [];
        queue.push(
          ...children.map((child) => ({
            item: child,
            dottedOrder: [
              task.dottedOrder,
              convertToDottedOrderFormat(
                child.startTime,
                child.id,
                child.executionOrder
              ),
            ].join("."),
            traceId: task.traceId,
          }))
        );
      }
    }

    Promise.all(
      sampled.map(([required, value]) => {
        const payload = { ...value, ...required };
        return this.client.createRun(payload);
      })
    ).then(
      () => resultCallback({ code: 0 }),
      (error) => resultCallback({ code: 1, error })
    );
  }

  async shutdown(): Promise<void> {
    // find nodes which are incomplete
    const incompleteNodes = Object.values(this.traceByMap).flatMap((trace) =>
      Object.values(trace.nodeMap).filter((i) => !i.sent)
    );

    if (incompleteNodes.length > 0) {
      console.warn(
        "Some incomplete nodes were found before shutdown and not sent to LangSmith."
      );
    }

    await this.client?.awaitPendingTraceBatches();
  }
  async forceFlush?(): Promise<void> {
    await this.client?.awaitPendingTraceBatches();
  }
}
