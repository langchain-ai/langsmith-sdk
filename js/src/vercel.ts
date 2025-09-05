import type {
  CoreAssistantMessage,
  CoreMessage,
  ToolCallPart,
  generateText,
} from "ai";
import type { AISDKSpan } from "./utils/vercel.types.js";
import { extractUsageMetadata } from "./utils/vercel.js";
import { Client, RunTree } from "./index.js";
import { KVMap, RunCreate } from "./schemas.js";
import { v5 as uuid5 } from "uuid";
import { getCurrentRunTree } from "./singletons/traceable.js";
import {
  getLangSmithEnvironmentVariable,
  getEnvironmentVariable,
} from "./utils/env.js";
import { isTracingEnabled } from "./env.js";
import {
  LANGSMITH_IS_ROOT,
  LANGSMITH_TRACEABLE_PARENT_OTEL_SPAN_ID,
} from "./experimental/otel/constants.js";

// eslint-disable-next-line @typescript-eslint/ban-types
type AnyString = string & {};

/** @deprecated Use `wrapAISDK` from `langsmith/experimental/vercel` instead. */
export type AITelemetrySettings = Exclude<
  Parameters<typeof generateText>[0]["experimental_telemetry"],
  undefined
>;

/** @deprecated Use `wrapAISDK` from `langsmith/experimental/vercel` instead. */
export interface TelemetrySettings extends AITelemetrySettings {
  /** ID of the run sent to LangSmith */
  runId?: string;
  /** Name of the run sent to LangSmith */
  runName?: string;
}

type LangChainMessageFields = {
  content:
    | string
    | Array<
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        Record<string, any> & { type?: "text" | "image_url" | AnyString }
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
            // Backcompat for AI SDK 4
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ...(part as any).experimental_providerMetadata,
          };
        }

        if (part.type === "tool-call") {
          // Backcompat for AI SDK 4
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const legacyToolCallInput = (part as any).args;
          return {
            type: "tool_use",
            name: part.toolName,
            id: part.toolCallId,
            input: legacyToolCallInput ?? part.input,
            // Backcompat for AI SDK 4
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ...(part as any).experimental_providerMetadata,
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
          // Backcompat for AI SDK 4
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const legacyToolCallInput = (part as any).args;
          return {
            id: part.toolCallId,
            type: "function",
            function: {
              name: part.toolName,
              id: part.toolCallId,
              arguments: JSON.stringify(legacyToolCallInput ?? part.input),
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
            // Backcompat for AI SDK 4
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ...(part as any).experimental_providerMetadata,
          };
        }

        if (part.type === "image") {
          let imageUrl = part.image;
          if (typeof imageUrl !== "string") {
            let uint8Array;
            if (
              imageUrl != null &&
              typeof imageUrl === "object" &&
              "type" in imageUrl &&
              "data" in imageUrl
            ) {
              // Typing is wrong here if a buffer is passed in
              uint8Array = new Uint8Array(imageUrl.data as Uint8Array);
            } else if (
              imageUrl != null &&
              typeof imageUrl === "object" &&
              Object.keys(imageUrl).every((key) => !isNaN(Number(key)))
            ) {
              // ArrayBuffers get turned into objects with numeric keys for some reason
              uint8Array = new Uint8Array(
                Array.from({
                  ...imageUrl,
                  length: Object.keys(imageUrl).length,
                })
              );
            }
            if (uint8Array) {
              let binary = "";
              for (let i = 0; i < uint8Array.length; i++) {
                binary += String.fromCharCode(uint8Array[i]);
              }
              imageUrl = btoa(binary);
            }
          }
          return {
            type: "image_url",
            image_url: imageUrl,
            // Backcompat for AI SDK 4
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ...(part as any).experimental_providerMetadata,
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
      // Backcompat for AI SDK 4
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const legacyToolCallResult = (toolCall as any).result;
      return {
        type: "tool",
        data: {
          content: JSON.stringify(legacyToolCallResult ?? toolCall.output),
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

function getDotOrder(item: {
  startTime: [seconds: number, nanoseconds: number];
  id: string;
  executionOrder: number;
}): string {
  const {
    startTime: [seconds, nanoseconds],
    id: runId,
    executionOrder,
  } = item;

  // Date only has millisecond precision, so we use the microseconds to break
  // possible ties, avoiding incorrect run order
  const nanosecondString = String(nanoseconds).padStart(9, "0");
  const msFull = Number(nanosecondString.slice(0, 6)) + executionOrder;
  const msString = String(msFull).padStart(6, "0");

  const ms = Number(msString.slice(0, -3));
  const ns = msString.slice(-3);

  return (
    stripNonAlphanumeric(
      `${new Date(seconds * 1000 + ms).toISOString().slice(0, -1)}${ns}Z`
    ) + runId
  );
}

function joinDotOrder(...segments: (string | undefined | null)[]): string {
  return segments.filter(Boolean).join(".");
}

function removeDotOrder(dotOrder: string, ...ids: string[]): string {
  return dotOrder
    .split(".")
    .filter((i) => !ids.some((id) => i.includes(id)))
    .join(".");
}

function reparentDotOrder(
  dotOrder: string,
  sourceRunId: string,
  parentDotOrder: string
): string {
  const segments = dotOrder.split(".");
  const sourceIndex = segments.findIndex((i) => i.includes(sourceRunId));

  if (sourceIndex === -1) return dotOrder;
  return joinDotOrder(
    ...parentDotOrder.split("."),
    ...segments.slice(sourceIndex)
  );
}

interface MutableRunCreate {
  id: string;
  trace_id: string;
  dotted_order: string;
  parent_run_id: string | undefined;
  start_time: string;
}

// Helper function to convert dotted order version of start time to ISO string
export const parseStrippedIsoTime = (stripped: string): string => {
  const year = stripped.slice(0, 4);
  const month = stripped.slice(4, 6);
  const day = stripped.slice(6, 8);
  const hour = stripped.slice(9, 11); // Skip 'T'
  const minute = stripped.slice(11, 13);
  const second = stripped.slice(13, 15);
  const ms = stripped.slice(15, 18); // milliseconds
  const us = stripped.length >= 21 ? stripped.slice(18, 21) : "000"; // microseconds

  // Create ISO string with microsecond precision only if microseconds are present
  return us !== "000"
    ? `${year}-${month}-${day}T${hour}:${minute}:${second}.${ms}${us}Z`
    : `${year}-${month}-${day}T${hour}:${minute}:${second}.${ms}Z`;
};

function getMutableRunCreate(dotOrder: string): MutableRunCreate {
  const segments = dotOrder.split(".").map((i) => {
    const [startTime, runId] = i.split("Z");
    return { startTime, runId };
  });

  const traceId = segments[0].runId;
  const parentRunId = segments.at(-2)?.runId;

  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  const lastSegment = segments.at(-1)!;
  const startTime = parseStrippedIsoTime(lastSegment.startTime);

  return {
    id: lastSegment.runId,
    trace_id: traceId,
    dotted_order: dotOrder,
    parent_run_id: parentRunId,
    start_time: startTime,
  };
}

function convertToTimestamp([seconds, nanoseconds]: [
  seconds: number,
  nanoseconds: number
]) {
  const ms = String(nanoseconds).slice(0, 3);
  return Number(String(seconds) + ms);
}

function sortByHr(a: AISDKSpan, b: AISDKSpan): number {
  if (a.startTime[0] !== b.startTime[0]) {
    return Math.sign(a.startTime[0] - b.startTime[0]);
  } else if (a.startTime[1] !== b.startTime[1]) {
    return Math.sign(a.startTime[1] - b.startTime[1]);
  } else if (getParentSpanId(a) === b.spanContext().spanId) {
    return -1;
  } else if (getParentSpanId(b) === a.spanContext().spanId) {
    return 1;
  } else {
    return 0;
  }
}

const ROOT = "$";
const RUN_ID_NAMESPACE = "5c718b20-9078-11ef-9a3d-325096b39f47";

const RUN_ID_METADATA_KEY = {
  input: "langsmith:runId",
  output: "ai.telemetry.metadata.langsmith:runId",
};

const RUN_NAME_METADATA_KEY = {
  input: "langsmith:runName",
  output: "ai.telemetry.metadata.langsmith:runName",
};

const TRACE_METADATA_KEY = {
  input: "langsmith:trace",
  output: "ai.telemetry.metadata.langsmith:trace",
};

const BAGGAGE_METADATA_KEY = {
  input: "langsmith:baggage",
  output: "ai.telemetry.metadata.langsmith:baggage",
};

const RESERVED_METADATA_KEYS = [
  RUN_ID_METADATA_KEY.output,
  RUN_NAME_METADATA_KEY.output,
  TRACE_METADATA_KEY.output,
  BAGGAGE_METADATA_KEY.output,
];

type PostProcessAction =
  | { type: "delete"; runId: string }
  | { type: "reparent"; runId: string; parentDotOrder: string }
  | { type: "rename"; sourceRunId: string; targetRunId: string };

interface RunTask {
  id: string;
  executionOrder: number;
  startTime: [seconds: number, nanoseconds: number];

  run: RunCreate | undefined;

  interop: InteropType | undefined;
  sent: boolean;
}

type InteropType =
  | { type: "traceable"; parentRunTree: RunTree }
  | { type: "user"; userRunId: string }
  | undefined;

function getParentSpanId(span: AISDKSpan): string | undefined {
  // Backcompat shim to support OTEL 1.x and 2.x
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (
    (span as any).parentSpanId ?? span.parentSpanContext?.spanId ?? undefined
  );
}

/**
 * @deprecated Use `wrapAISDK` from `langsmith/experimental/vercel` instead.
 * OpenTelemetry trace exporter for Vercel AI SDK.
 *
 * @example
 * ```ts
 * import { AISDKExporter } from "langsmith/vercel";
 * import { Client } from "langsmith";
 *
 * import { generateText } from "ai";
 * import { openai } from "@ai-sdk/openai";
 *
 * import { NodeSDK } from "@opentelemetry/sdk-node";
 * import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
 *
 * const client = new Client();
 *
 * const sdk = new NodeSDK({
 *   traceExporter: new AISDKExporter({ client }),
 *   instrumentations: [getNodeAutoInstrumentations()],
 * });
 *
 * sdk.start();
 *
 * const res = await generateText({
 *   model: openai("gpt-4o-mini"),
 *   messages: [
 *     {
 *       role: "user",
 *       content: "What color is the sky?",
 *     },
 *   ],
 *   experimental_telemetry: AISDKExporter.getSettings({
 *     runName: "langsmith_traced_call",
 *     metadata: { userId: "123", language: "english" },
 *   }),
 * });
 *
 * await sdk.shutdown();
 * ```
 */
export class AISDKExporter {
  private client: Client;
  private traceByMap: Record<
    string,
    {
      childMap: Record<string, RunTask[]>;
      nodeMap: Record<string, RunTask>;
      relativeExecutionOrder: Record<string, number>;
    }
  > = {};
  private seenSpanInfo: Record<
    string,
    { span: AISDKSpan; dotOrder: string; sent: boolean; projectName?: string }
  > = {};

  private pendingSpans: Record<string, AISDKSpan> = {};

  private debug: boolean;

  private projectName?: string;

  constructor(args?: {
    client?: Client;
    debug?: boolean;
    projectName?: string;
  }) {
    this.client = args?.client ?? new Client();
    this.debug =
      args?.debug ?? getEnvironmentVariable("OTEL_LOG_LEVEL") === "DEBUG";
    this.projectName = args?.projectName;

    this.logDebug("creating exporter", { tracingEnabled: isTracingEnabled() });
  }

  static getSettings(settings?: TelemetrySettings) {
    const { runId, runName, ...rest } = settings ?? {};
    const metadata = { ...rest?.metadata };
    if (runId != null) metadata[RUN_ID_METADATA_KEY.input] = runId;
    if (runName != null) metadata[RUN_NAME_METADATA_KEY.input] = runName;

    // attempt to obtain the run tree if used within a traceable function
    let defaultEnabled = settings?.isEnabled ?? isTracingEnabled();
    try {
      const runTree = getCurrentRunTree();
      const headers = runTree.toHeaders();
      metadata[TRACE_METADATA_KEY.input] = headers["langsmith-trace"];
      metadata[BAGGAGE_METADATA_KEY.input] = headers["baggage"];

      // honor the tracingEnabled flag if coming from traceable
      if (runTree.tracingEnabled != null) {
        defaultEnabled = runTree.tracingEnabled;
      }
    } catch {
      // pass
    }

    if (
      metadata[RUN_ID_METADATA_KEY.input] &&
      metadata[TRACE_METADATA_KEY.input]
    ) {
      throw new Error(
        "Cannot provide `runId` when used within traceable function."
      );
    }

    return { ...rest, isEnabled: rest.isEnabled ?? defaultEnabled, metadata };
  }

  /** @internal */
  protected getSpanAttributeKey = (
    span: AISDKSpan,
    key: string
  ): string | undefined => {
    const attributes = span.attributes as Record<string, unknown>;

    return key in attributes && typeof attributes[key] === "string"
      ? (attributes[key] as string)
      : undefined;
  };

  /** @internal */
  protected parseInteropFromMetadata(
    span: AISDKSpan,
    parentSpan?: AISDKSpan
  ): InteropType {
    if (!this.isRootRun(span)) return undefined;

    if (parentSpan?.name === "ai.toolCall") {
      return undefined;
    }

    const userTraceId = this.getSpanAttributeKey(
      span,
      RUN_ID_METADATA_KEY.output
    );
    const parentTrace = this.getSpanAttributeKey(
      span,
      TRACE_METADATA_KEY.output
    );

    if (parentTrace && userTraceId) {
      throw new Error(
        `Cannot provide both "${RUN_ID_METADATA_KEY.input}" and "${TRACE_METADATA_KEY.input}" metadata keys.`
      );
    }

    if (parentTrace) {
      const parentRunTree = RunTree.fromHeaders({
        "langsmith-trace": parentTrace,
        baggage:
          this.getSpanAttributeKey(span, BAGGAGE_METADATA_KEY.output) || "",
      });

      if (!parentRunTree)
        throw new Error("Unreachable code: empty parent run tree");
      return { type: "traceable", parentRunTree };
    }

    if (userTraceId) return { type: "user", userRunId: userTraceId };
    return undefined;
  }

  /** @internal */
  protected getRunCreate(
    span: AISDKSpan,
    projectName?: string
  ): RunCreate | undefined {
    const asRunCreate = (rawConfig: RunCreate) => {
      const aiMetadata = Object.keys(span.attributes)
        .filter(
          (key) =>
            key.startsWith("ai.telemetry.metadata.") &&
            !RESERVED_METADATA_KEYS.includes(key)
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

      const parsedStart = convertToTimestamp(span.startTime);
      const parsedEnd = convertToTimestamp(span.endTime);

      let name = rawConfig.name;

      // if user provided a custom name, only use it if it's the root
      if (this.isRootRun(span)) {
        name =
          this.getSpanAttributeKey(span, RUN_NAME_METADATA_KEY.output) || name;
      }

      const config: RunCreate = {
        ...rawConfig,
        name,
        extra: {
          ...rawConfig.extra,
          metadata: {
            ...rawConfig.extra?.metadata,
            ...aiMetadata,
            "ai.operationId": span.attributes["ai.operationId"],
          },
        },
        session_name:
          projectName ??
          this.projectName ??
          getLangSmithEnvironmentVariable("PROJECT") ??
          getLangSmithEnvironmentVariable("SESSION"),
        start_time: Math.min(parsedStart, parsedEnd),
        end_time: Math.max(parsedStart, parsedEnd),
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
            let content = tryJson(span.attributes["ai.response.toolCalls"]);

            if (Array.isArray(content)) {
              content = content.map((i) => ({
                type: "tool-call",
                ...i,
                args: tryJson(i.args),
              }));
            }

            result = {
              llm_output: convertCoreToSmith({
                role: "assistant",
                content,
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

          return result;
        })();

        const invocationParams = ((): KVMap | undefined => {
          if ("ai.prompt.tools" in span.attributes) {
            return {
              tools: span.attributes["ai.prompt.tools"].flatMap((tool) => {
                try {
                  return JSON.parse(tool);
                } catch {
                  // pass
                }
                return [];
              }),
            };
          }
          return {};
        })();

        const events: KVMap[] = [];
        const firstChunkEvent = span.events.find(
          (i) => i.name === "ai.stream.firstChunk"
        );
        if (firstChunkEvent) {
          events.push({
            name: "new_token",
            time: convertToTimestamp(firstChunkEvent.time),
          });
        }

        const runType =
          span.name === "ai.generateText" || span.name === "ai.streamText"
            ? "chain"
            : "llm";

        const error = span.status?.code === 2 ? span.status.message : undefined;
        const usageMetadata = extractUsageMetadata(span as KVMap);

        // TODO: add first_token_time
        return asRunCreate({
          run_type: runType,
          name: span.attributes["ai.model.provider"],
          error,
          inputs,
          outputs,
          events,
          extra: {
            invocation_params: invocationParams,
            batch_size: 1,
            metadata: {
              usage_metadata: usageMetadata,
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

      case "ai.toolCall": {
        const args = tryJson(
          span.attributes["ai.toolCall.input"] ??
            span.attributes["ai.toolCall.args"]
        );
        let inputs: KVMap = { args };

        if (typeof args === "object" && args != null) {
          inputs = args;
        }

        const output = tryJson(
          span.attributes["ai.toolCall.output"] ??
            span.attributes["ai.toolCall.result"]
        );
        let outputs: KVMap = { output };

        if (typeof output === "object" && output != null) {
          outputs = output;
        }

        const error = span.status?.code === 2 ? span.status.message : undefined;

        return asRunCreate({
          run_type: "tool",
          name: span.attributes["ai.toolCall.name"],
          error,
          extra: error
            ? {
                metadata: {
                  usage_metadata: {
                    input_tokens: 0,
                    output_tokens: 0,
                    total_tokens: 0,
                  },
                },
              }
            : undefined,
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

          return result;
        })();

        const events: KVMap[] = [];
        const firstChunkEvent = span.events.find(
          (i) => i.name === "ai.stream.firstChunk"
        );
        if (firstChunkEvent) {
          events.push({
            name: "new_token",
            time: convertToTimestamp(firstChunkEvent.time),
          });
        }

        const runType =
          span.name === "ai.generateObject" || span.name === "ai.streamObject"
            ? "chain"
            : "llm";

        const error = span.status?.code === 2 ? span.status.message : undefined;
        const usageMetadata = extractUsageMetadata(span as KVMap);

        return asRunCreate({
          run_type: runType,
          name: span.attributes["ai.model.provider"],
          error,
          inputs,
          outputs,
          events,
          extra: {
            batch_size: 1,
            metadata: {
              usage_metadata: usageMetadata,
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
        return undefined;
    }
  }

  /** @internal */
  protected isRootRun(span: AISDKSpan): boolean {
    switch (span.name) {
      case "ai.generateText":
      case "ai.streamText":
      case "ai.generateObject":
      case "ai.streamObject":
      case "ai.embed":
      case "ai.embedMany":
        return true;
      default:
        return false;
    }
  }

  _export(
    spans: unknown[],
    resultCallback: (result: { code: 0 | 1; error?: Error }) => void
  ): void {
    this.logDebug("exporting spans", spans);

    const typedSpans = (spans as AISDKSpan[])
      .concat(Object.values(this.pendingSpans))
      .slice()
      // Parent spans should go before child spans in the final order,
      // but may have the same exact start time as their children.
      // They will end earlier, so break ties by end time.
      // TODO: Figure out why this happens.
      .sort((a, b) => sortByHr(a, b));
    for (const span of typedSpans) {
      const { traceId, spanId } = span.spanContext();
      const runId = uuid5(spanId, RUN_ID_NAMESPACE);

      let parentId = getParentSpanId(span);
      if (LANGSMITH_IS_ROOT in span.attributes) {
        parentId = undefined;
      } else if (
        LANGSMITH_TRACEABLE_PARENT_OTEL_SPAN_ID in span.attributes &&
        typeof span.attributes[LANGSMITH_TRACEABLE_PARENT_OTEL_SPAN_ID] ===
          "string"
      ) {
        parentId = span.attributes[LANGSMITH_TRACEABLE_PARENT_OTEL_SPAN_ID];
      }
      let parentRunId = parentId
        ? uuid5(parentId, RUN_ID_NAMESPACE)
        : undefined;
      let parentSpanInfo = parentRunId
        ? this.seenSpanInfo[parentRunId]
        : undefined;

      // Unrelated, untraced spans should behave as passthroughs from LangSmith's perspective.
      while (
        parentSpanInfo != null &&
        this.getRunCreate(parentSpanInfo.span) == null
      ) {
        parentId = getParentSpanId(parentSpanInfo.span);
        if (parentId == null) {
          break;
        }
        parentRunId = parentId ? uuid5(parentId, RUN_ID_NAMESPACE) : undefined;
        parentSpanInfo = parentRunId
          ? this.seenSpanInfo[parentRunId]
          : undefined;
      }

      // Export may be called in any order, so we need to queue any spans with missing parents
      // for retry later in order to determine whether their parents are tool calls
      // and should not be reparented below.
      if (parentRunId !== undefined && parentSpanInfo === undefined) {
        this.pendingSpans[spanId] = span;
        continue;
      } else {
        delete this.pendingSpans[spanId];
      }

      this.traceByMap[traceId] ??= {
        childMap: {},
        nodeMap: {},
        relativeExecutionOrder: {},
      };

      const traceMap = this.traceByMap[traceId];

      traceMap.relativeExecutionOrder[parentRunId ?? ROOT] ??= -1;
      traceMap.relativeExecutionOrder[parentRunId ?? ROOT] += 1;

      const interop = this.parseInteropFromMetadata(span, parentSpanInfo?.span);

      const projectName =
        (interop?.type === "traceable"
          ? interop.parentRunTree.project_name
          : undefined) ?? parentSpanInfo?.projectName;
      const run = this.getRunCreate(span, projectName);

      traceMap.nodeMap[runId] ??= {
        id: runId,
        startTime: span.startTime,
        run,
        sent: false,
        interop,
        executionOrder: traceMap.relativeExecutionOrder[parentRunId ?? ROOT],
      };

      if (this.seenSpanInfo[runId] == null) {
        this.seenSpanInfo[runId] = {
          span,
          dotOrder: joinDotOrder(
            parentSpanInfo?.dotOrder,
            getDotOrder(traceMap.nodeMap[runId])
          ),
          projectName,
          sent: false,
        };
      }

      if (this.debug) console.log(`[${span.name}] ${runId}`, run);
      traceMap.childMap[parentRunId ?? ROOT] ??= [];
      traceMap.childMap[parentRunId ?? ROOT].push(traceMap.nodeMap[runId]);
    }

    const sampled: RunCreate[] = [];
    const actions: PostProcessAction[] = [];

    for (const traceId of Object.keys(this.traceByMap)) {
      const traceMap = this.traceByMap[traceId];
      const queue: RunTask[] = Object.keys(traceMap.childMap)
        .map((runId) => {
          if (runId === ROOT) {
            return traceMap.childMap[runId];
          }
          return [];
        })
        .flat();

      const seen = new Set<string>();
      while (queue.length) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        const task = queue.shift()!;
        if (seen.has(task.id)) continue;

        let taskDotOrder = this.seenSpanInfo[task.id].dotOrder;
        if (!task.sent) {
          if (task.run != null) {
            if (task.interop?.type === "user") {
              actions.push({
                type: "rename",
                sourceRunId: task.id,
                targetRunId: task.interop.userRunId,
              });
            }

            if (task.interop?.type === "traceable") {
              actions.push({
                type: "reparent",
                runId: task.id,
                parentDotOrder: task.interop.parentRunTree.dotted_order,
              });
            }

            for (const action of actions) {
              if (action.type === "delete") {
                taskDotOrder = removeDotOrder(taskDotOrder, action.runId);
              }

              if (action.type === "reparent") {
                taskDotOrder = reparentDotOrder(
                  taskDotOrder,
                  action.runId,
                  action.parentDotOrder
                );
              }

              if (action.type === "rename") {
                taskDotOrder = taskDotOrder.replace(
                  action.sourceRunId,
                  action.targetRunId
                );
              }
            }

            this.seenSpanInfo[task.id].dotOrder = taskDotOrder;
            if (!this.seenSpanInfo[task.id].sent) {
              sampled.push({
                ...task.run,
                ...getMutableRunCreate(taskDotOrder),
              });
            }
            this.seenSpanInfo[task.id].sent = true;
          } else {
            actions.push({ type: "delete", runId: task.id });
          }

          task.sent = true;
        }

        const children = traceMap.childMap[task.id] ?? [];
        queue.push(...children);
      }
    }

    this.logDebug(`sampled runs to be sent to LangSmith`, sampled);
    Promise.all(sampled.map((run) => this.client.createRun(run))).then(
      () => resultCallback({ code: 0 }),
      (error) => resultCallback({ code: 1, error })
    );
  }

  export(
    spans: unknown[],
    resultCallback: (result: { code: 0 | 1; error?: Error }) => void
  ): void {
    this._export(spans, (result) => {
      if (result.code === 0) {
        // Empty export to try flushing pending spans to rule out any trace order shenanigans
        this._export([], resultCallback);
      } else {
        resultCallback(result);
      }
    });
  }

  async shutdown(): Promise<void> {
    // find nodes which are incomplete
    const incompleteNodes = Object.values(this.traceByMap).flatMap((trace) =>
      Object.values(trace.nodeMap).filter((i) => !i.sent && i.run != null)
    );

    this.logDebug("shutting down", { incompleteNodes });

    if (incompleteNodes.length > 0) {
      console.warn(
        "Some incomplete nodes were found before shutdown and not sent to LangSmith."
      );
    }

    await this.forceFlush();
  }

  async forceFlush(): Promise<void> {
    await new Promise((resolve) => {
      this.export([], resolve);
    });
    await this.client.awaitPendingTraceBatches();
  }

  protected logDebug(...args: Parameters<typeof console.debug>): void {
    if (!this.debug) return;
    console.debug(`[${new Date().toISOString()}] [LangSmith]`, ...args);
  }
}
