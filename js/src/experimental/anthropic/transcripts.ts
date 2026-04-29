import { readFile } from "node:fs/promises";

import {
  convertFromAnthropicMessage,
  type LangSmithMessage,
} from "./messages.js";
import type { SDKAssistantMessage, SDKUserMessage } from "./types.js";
import { extractUsageMetadata } from "./usage.js";

export type TranscriptAssistantTurn = {
  messageId: string;
  model?: string;
  content: Record<string, unknown>[];
  usage?: Record<string, unknown>;
  usageMetadata?: Record<string, unknown>;
  timestamp?: number;
  inputMessages: LangSmithMessage[];
  message: SDKAssistantMessage;
};

export type TranscriptToolResult = {
  toolUseId: string;
  content: unknown;
  isError?: boolean;
};

export type TranscriptData = {
  turns: TranscriptAssistantTurn[];
  usageByMessageId: Record<string, Record<string, unknown>>;
  toolResults: TranscriptToolResult[];
};

function parseTimestamp(value: unknown): number | undefined {
  if (typeof value !== "string" || value.length === 0) return undefined;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? undefined : timestamp;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value != null && !Array.isArray(value);
}

function toSDKAssistantMessage(
  data: Record<string, unknown>,
): SDKAssistantMessage | undefined {
  const message = data.message;
  if (!isRecord(message)) return undefined;

  const id = message.id;
  if (typeof id !== "string" || id.length === 0) return undefined;

  return {
    type: "assistant",
    parent_tool_use_id:
      typeof data.parent_tool_use_id === "string"
        ? data.parent_tool_use_id
        : null,
    message: {
      ...(message as SDKAssistantMessage["message"]),
      id,
      content: Array.isArray(message.content)
        ? (message.content as Record<string, unknown>[])
        : [],
    },
  };
}

function toSDKUserMessage(
  data: Record<string, unknown>,
): SDKUserMessage | undefined {
  const message = data.message;
  if (!isRecord(message)) return undefined;

  return {
    type: "user",
    parent_tool_use_id:
      typeof data.parent_tool_use_id === "string"
        ? data.parent_tool_use_id
        : null,
    session_id: typeof data.session_id === "string" ? data.session_id : "",
    message: message as SDKUserMessage["message"],
    tool_use_result: data.tool_use_result,
  };
}

/**
 * Read a Claude Agent SDK JSONL transcript and return final assistant turns,
 * final usage by message id, and tool_result blocks.
 *
 * The transcript format is not a contracted SDK API. This mirrors the Python
 * reconciler and is intentionally best-effort: malformed lines and unreadable
 * files are ignored so tracing never affects the user conversation.
 * @internal
 */
export async function readTranscript(
  filePath: string,
): Promise<TranscriptData> {
  let contents: string;
  try {
    contents = await readFile(filePath, "utf8");
  } catch {
    return { turns: [], usageByMessageId: {}, toolResults: [] };
  }

  const entriesById = new Map<string, TranscriptAssistantTurn>();
  const usageByMessageId: Record<string, Record<string, unknown>> = {};
  const toolResults: TranscriptToolResult[] = [];
  const conversation: LangSmithMessage[] = [];

  for (const line of contents.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    let data: unknown;
    try {
      data = JSON.parse(trimmed);
    } catch {
      continue;
    }
    if (!isRecord(data)) continue;

    if (data.type === "user") {
      const sdkMessage = toSDKUserMessage(data);
      if (sdkMessage == null) continue;

      const content = sdkMessage.message.content;
      const toolUseResultIsError = isRecord(sdkMessage.tool_use_result)
        ? sdkMessage.tool_use_result.is_error === true ||
          sdkMessage.tool_use_result.isError === true
        : false;
      if (Array.isArray(content)) {
        for (const block of content) {
          if (!isRecord(block) || block.type !== "tool_result") continue;
          const toolUseId = block.tool_use_id;
          if (typeof toolUseId !== "string") continue;
          toolResults.push({
            toolUseId,
            content: block.content,
            isError:
              block.is_error === true ||
              block.isError === true ||
              toolUseResultIsError,
          });
        }
      }

      conversation.push(...convertFromAnthropicMessage(sdkMessage));
      continue;
    }

    if (data.type !== "assistant") continue;

    const sdkMessage = toSDKAssistantMessage(data);
    if (sdkMessage == null) continue;

    const messageId = sdkMessage.message.id;
    const rawUsage = sdkMessage.message.usage;
    if (rawUsage != null) {
      usageByMessageId[messageId] = extractUsageMetadata(rawUsage);
    }

    const turn: TranscriptAssistantTurn = {
      messageId,
      model: sdkMessage.message.model,
      content: sdkMessage.message.content,
      usage: rawUsage,
      usageMetadata:
        rawUsage != null ? extractUsageMetadata(rawUsage) : undefined,
      timestamp: parseTimestamp(data.timestamp),
      inputMessages: conversation.slice(),
      message: sdkMessage,
    };
    // Always overwrite. The final chunk (where stop_reason is set) appears last.
    entriesById.set(messageId, turn);

    if (sdkMessage.message.stop_reason) {
      conversation.push(...convertFromAnthropicMessage(sdkMessage));
    }
  }

  return {
    turns: Array.from(entriesById.values()).filter(
      (turn) => turn.message.message.stop_reason,
    ),
    usageByMessageId,
    toolResults,
  };
}
