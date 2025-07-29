import type { ReadableSpan } from "@opentelemetry/sdk-trace-base";

// eslint-disable-next-line @typescript-eslint/ban-types
type AnyString = string & {};

interface TypedReadableSpan<Name, Attributes>
  extends Omit<ReadableSpan, "name" | "attributes"> {
  name: Name;
  attributes: Attributes;
}

interface BaseLLMSpanAttributes {
  "ai.model.id": string;
  "ai.model.provider": string;

  "ai.usage.promptTokens": number;
  "ai.usage.completionTokens": number;
  "ai.response.providerMetadata"?: string;

  "ai.telemetry.functionId"?: string;
  "resource.name"?: string;
}

interface CallLLMSpanAttributes extends BaseLLMSpanAttributes {
  "ai.response.model": string;
  "ai.response.id": string;
  "ai.response.timestamp": number;
}

interface BaseEmbedSpanAttributes {
  "ai.model.id": string;
  "ai.model.provider": string;
  "ai.usage.tokens": number;

  "ai.telemetry.functionId"?: string;
  "resource.name"?: string;
}

type ToolCallSpan = TypedReadableSpan<
  "ai.toolCall",
  {
    "operation.name": "ai.toolCall";
    "ai.operationId": "ai.toolCall";
    "ai.toolCall.name": string;
    "ai.toolCall.id": string;
    "ai.toolCall.input"?: string;
    "ai.toolCall.output"?: string;
    /** @deprecated AI SDK 4 span */
    "ai.toolCall.args"?: string;
    /** @deprecated AI SDK 4 span */
    "ai.toolCall.result"?: string;
  }
>;

type GenerateTextSpan = TypedReadableSpan<
  "ai.generateText",
  BaseLLMSpanAttributes & {
    "operation.name": "ai.generateText";
    "ai.operationId": "ai.generateText";
    "ai.prompt": string;
    "ai.response.text": string;
    "ai.response.toolCalls": string;
    "ai.response.finishReason": string;
    "ai.settings.maxSteps": number;
  }
>;

type DoGenerateTextSpan = TypedReadableSpan<
  "ai.generateText.doGenerate",
  CallLLMSpanAttributes & {
    "operation.name": "ai.generateText.doGenerate";
    "ai.operationId": "ai.generateText.doGenerate";
    "ai.prompt.format": string;
    "ai.prompt.messages": string;
    "ai.prompt.tools": string[];
    "ai.response.text": string;
    "ai.response.toolCalls": string;
    "ai.response.finishReason": string;
  }
>;

type StreamTextSpan = TypedReadableSpan<
  "ai.streamText",
  BaseLLMSpanAttributes & {
    "operation.name": "ai.streamText";
    "ai.operationId": "ai.streamText";
    "ai.prompt": string;
    "ai.response.text": string;
    "ai.response.toolCalls": string;
    "ai.response.finishReason": string;
    "ai.settings.maxSteps": number;
  }
>;

type DoStreamTextSpan = TypedReadableSpan<
  "ai.streamText.doStream",
  CallLLMSpanAttributes & {
    "operation.name": "ai.streamText.doStream";
    "ai.operationId": "ai.streamText.doStream";
    "ai.prompt.format": string;
    "ai.prompt.messages": string;
    "ai.prompt.tools": string[];
    "ai.response.text": string;
    "ai.response.toolCalls": string;
    "ai.response.msToFirstChunk": number;
    "ai.response.msToFinish": number;
    "ai.response.avgCompletionTokensPerSecond": number;
    "ai.response.finishReason": string;
  }
>;

type GenerateObjectSpan = TypedReadableSpan<
  "ai.generateObject",
  BaseLLMSpanAttributes & {
    "operation.name": "ai.generateObject";
    "ai.operationId": "ai.generateObject";
    "ai.prompt": string;

    "ai.schema": string;
    "ai.schema.name": string;
    "ai.schema.description": string;

    "ai.response.object": string;

    "ai.settings.mode": "json" | AnyString;
    "ai.settings.output": "object" | "no-schema" | AnyString;
  }
>;
type DoGenerateObjectSpan = TypedReadableSpan<
  "ai.generateObject.doGenerate",
  CallLLMSpanAttributes & {
    "operation.name": "ai.generateObject.doGenerate";
    "ai.operationId": "ai.generateObject.doGenerate";

    "ai.prompt.format": string;
    "ai.prompt.messages": string;

    "ai.response.object": string;
    "ai.response.finishReason": string;

    "ai.settings.mode": "json" | AnyString;
    "ai.settings.output": "object" | "no-schema" | AnyString;
  }
>;

type StreamObjectSpan = TypedReadableSpan<
  "ai.streamObject",
  BaseLLMSpanAttributes & {
    "operation.name": "ai.streamObject";
    "ai.operationId": "ai.streamObject";
    "ai.prompt": string;

    "ai.schema": string;
    "ai.schema.name": string;
    "ai.schema.description": string;

    "ai.response.object": string;

    "ai.settings.mode": "json" | AnyString;
    "ai.settings.output": "object" | "no-schema" | AnyString;
  }
>;
type DoStreamObjectSpan = TypedReadableSpan<
  "ai.streamObject.doStream",
  CallLLMSpanAttributes & {
    "operation.name": "ai.streamObject.doStream";
    "ai.operationId": "ai.streamObject.doStream";

    "ai.prompt.format": string;
    "ai.prompt.messages": string;

    "ai.response.object": string;
    "ai.response.finishReason": string;
    "ai.response.msToFirstChunk": number;

    "ai.settings.mode": "json" | AnyString;
  }
>;

type EmbedSpan = TypedReadableSpan<
  "ai.embed",
  BaseEmbedSpanAttributes & {
    "operation.name": "ai.embed";
    "ai.operationId": "ai.embed";

    "ai.value": string;
    "ai.embedding": string;
  }
>;

type DoEmbedSpan = TypedReadableSpan<
  "ai.embed.doEmbed",
  BaseEmbedSpanAttributes & {
    "operation.name": "ai.embed.doEmbed";
    "ai.operationId": "ai.embed.doEmbed";

    "ai.values": string[];
    "ai.embeddings": string[];
  }
>;

type EmbedManySpan = TypedReadableSpan<
  "ai.embedMany",
  BaseEmbedSpanAttributes & {
    "operation.name": "ai.embedMany";
    "ai.operationId": "ai.embedMany";

    "ai.values": string[];
    "ai.embeddings": string[];
  }
>;

type DoEmbedManySpan = TypedReadableSpan<
  "ai.embedMany.doEmbed",
  BaseEmbedSpanAttributes & {
    "operation.name": "ai.embedMany.doEmbed";
    "ai.operationId": "ai.embedMany.doEmbed";

    "ai.values": string[];
    "ai.embeddings": string[];
  }
>;

/** @internal */
export type AISDKSpan =
  | ToolCallSpan
  | GenerateTextSpan
  | DoGenerateTextSpan
  | StreamTextSpan
  | DoStreamTextSpan
  | GenerateObjectSpan
  | DoGenerateObjectSpan
  | StreamObjectSpan
  | DoStreamObjectSpan
  | EmbedSpan
  | DoEmbedSpan
  | EmbedManySpan
  | DoEmbedManySpan;
