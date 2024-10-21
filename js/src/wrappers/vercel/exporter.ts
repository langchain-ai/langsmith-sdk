import type { ReadableSpan, SpanExporter } from "@opentelemetry/sdk-trace-base";
import type { ExportResult } from "@opentelemetry/core";
import type { CoreAssistantMessage, CoreMessage, ToolCallPart } from "ai";
import type { AISDKSpan } from "./exporter.types.js";
import { Client, RunTree, RunTreeConfig } from "../../index.js";
import { KVMap } from "../../schemas.js";
import { AsyncLocalStorageProviderSingleton } from "../../singletons/traceable.js";

function assertNever(x: never): never {
  throw new Error("Unreachable state: " + x);
}

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

const sortByHrTime = (a: ReadableSpan, b: ReadableSpan) => {
  return (
    Math.sign(a.startTime[0] - b.startTime[0]) ||
    Math.sign(a.startTime[1] - b.startTime[1])
  );
};

export class LangSmithAISDKExporter implements SpanExporter {
  private client: Client | undefined;

  constructor(args?: { client?: Client }) {
    this.client = args?.client;
  }

  export(
    spans: ReadableSpan[],
    resultCallback: (result: ExportResult) => void
  ): void {
    const runTreeMap: Record<string, RunTree> = {};
    const sortedSpans = [...spans].sort(sortByHrTime) as AISDKSpan[];

    for (const span of sortedSpans) {
      const spanId = span.spanContext().spanId;
      const parentSpanId = span.parentSpanId;
      let parentRunTree = parentSpanId ? runTreeMap[parentSpanId] : null;

      if (parentRunTree == null) {
        try {
          parentRunTree =
            AsyncLocalStorageProviderSingleton.getInstance().getStore() ?? null;
        } catch {
          // pass
        }
      }

      const toRunTree = (rawConfig: RunTreeConfig) => {
        const aiMetadata = Object.keys(span.attributes)
          .filter((key) => key.startsWith("ai.telemetry.metadata."))
          .reduce((acc, key) => {
            acc[key.slice("ai.telemetry.metadata.".length)] =
              span.attributes[key as keyof typeof span.attributes];

            return acc;
          }, {} as Record<string, unknown>);

        if (
          ("ai.telemetry.functionId" in span.attributes &&
            span.attributes["ai.telemetry.functionId"]) ||
          ("resource.name" in span.attributes &&
            span.attributes["resource.name"])
        ) {
          aiMetadata["functionId"] =
            span.attributes["ai.telemetry.functionId"] ||
            span.attributes["resource.name"];
        }

        const config: RunTreeConfig = {
          ...rawConfig,
          metadata: {
            ...rawConfig.metadata,
            ...aiMetadata,
            "ai.operationId": span.attributes["ai.operationId"],
          },
          start_time: +(
            String(span.startTime[0]) + String(span.startTime[1]).slice(0, 3)
          ),
          end_time: +(
            String(span.endTime[0]) + String(span.endTime[1]).slice(0, 3)
          ),
          client: this.client,
        };
        const runTree =
          parentRunTree?.createChild(config) ?? new RunTree(config);
        this.client ??= runTree.client;

        return runTree;
      };

      switch (span.name) {
        case "ai.generateText.doGenerate":
        case "ai.generateText":
        case "ai.streamText.doStream":
        case "ai.streamText": {
          const inputs = ((): KVMap | undefined => {
            if ("ai.prompt.messages" in span.attributes) {
              return {
                messages: tryJson(
                  span.attributes["ai.prompt.messages"]
                ).flatMap((i: CoreMessage) => convertCoreToSmith(i)),
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

            return undefined;
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
          runTreeMap[spanId] = toRunTree({
            run_type: "llm",
            name: span.attributes["ai.model.provider"],
            inputs,
            outputs,
            metadata: {
              ls_provider: span.attributes["ai.model.provider"]
                .split(".")
                .at(0),
              ls_model_type: span.attributes["ai.model.provider"]
                .split(".")
                .at(1),
              ls_model_name: span.attributes["ai.model.id"],
            },
            extra: { batch_size: 1 },
          });
          break;
        }

        case "ai.toolCall": {
          const args = tryJson(span.attributes["ai.toolCall.args"]);
          let inputs: KVMap | undefined = { args };

          if (typeof args === "object" && args != null) {
            inputs = args;
          }

          const output = tryJson(span.attributes["ai.toolCall.result"]);
          let outputs: KVMap | undefined = { output };

          if (typeof output === "object" && output != null) {
            outputs = output;
          }

          runTreeMap[spanId] = toRunTree({
            run_type: "tool",
            name: span.attributes["ai.toolCall.name"],
            inputs,
            outputs,
          });
          break;
        }

        case "ai.streamObject":
        case "ai.streamObject.doStream":
        case "ai.generateObject":
        case "ai.generateObject.doGenerate": {
          const inputs = ((): KVMap | undefined => {
            if ("ai.prompt.messages" in span.attributes) {
              return {
                messages: tryJson(
                  span.attributes["ai.prompt.messages"]
                ).flatMap((i: CoreMessage) => convertCoreToSmith(i)),
              };
            }

            if ("ai.prompt" in span.attributes) {
              return { input: tryJson(span.attributes["ai.prompt"]) };
            }

            return undefined;
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

          runTreeMap[spanId] = toRunTree({
            run_type: "llm",
            name: span.attributes["ai.model.provider"],
            inputs,
            outputs,
            metadata: {
              ls_provider: span.attributes["ai.model.provider"]
                .split(".")
                .at(0),
              ls_model_type: span.attributes["ai.model.provider"]
                .split(".")
                .at(1),
              ls_model_name: span.attributes["ai.model.id"],
            },
            extra: { batch_size: 1 },
          });
          break;
        }

        case "ai.embed": {
          runTreeMap[spanId] = toRunTree({
            run_type: "chain",
            name: span.attributes["ai.model.provider"],
            inputs: { value: tryJson(span.attributes["ai.value"]) },
            outputs: { embedding: tryJson(span.attributes["ai.embedding"]) },
          });
          break;
        }
        case "ai.embed.doEmbed":
        case "ai.embedMany":
        case "ai.embedMany.doEmbed": {
          runTreeMap[spanId] = toRunTree({
            run_type: "chain",
            name: span.attributes["ai.model.provider"],
            inputs: { values: span.attributes["ai.values"].map(tryJson) },
            outputs: {
              embeddings: span.attributes["ai.embeddings"].map(tryJson),
            },
          });
          break;
        }

        default:
          assertNever(span);
      }
    }

    Promise.all(
      Object.values(runTreeMap).map((runTree) => runTree.postRun())
    ).then(
      () => resultCallback({ code: 0 }),
      (error) => resultCallback({ code: 1, error })
    );
  }

  async shutdown(): Promise<void> {
    await this.client?.awaitPendingTraceBatches();
  }
  async forceFlush?(): Promise<void> {
    await this.client?.awaitPendingTraceBatches();
  }
}
