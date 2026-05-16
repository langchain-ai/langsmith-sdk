/* eslint-disable import/no-extraneous-dependencies */
import type { LanguageModelV2DataContent } from "@ai-sdk/provider";
import type { ModelMessage, ToolCallPart } from "ai";
import { isRecord } from "../../utils/types.js";

const guessMimetypeFromBase64 = (data: string) => {
  // Check magic bytes from base64 data
  const bytes = atob(data.substring(0, 20)); // Decode first few bytes

  // PNG: 89 50 4E 47
  if (
    bytes.charCodeAt(0) === 0x89 &&
    bytes.charCodeAt(1) === 0x50 &&
    bytes.charCodeAt(2) === 0x4e &&
    bytes.charCodeAt(3) === 0x47
  ) {
    return "image/png";
  }

  // JPEG: FF D8 FF
  if (
    bytes.charCodeAt(0) === 0xff &&
    bytes.charCodeAt(1) === 0xd8 &&
    bytes.charCodeAt(2) === 0xff
  ) {
    return "image/jpeg";
  }

  // GIF: 47 49 46 38
  if (
    bytes.charCodeAt(0) === 0x47 &&
    bytes.charCodeAt(1) === 0x49 &&
    bytes.charCodeAt(2) === 0x46 &&
    bytes.charCodeAt(3) === 0x38
  ) {
    return "image/gif";
  }

  // WebP: 52 49 46 46 (RIFF) ... 57 45 42 50 (WEBP)
  if (
    bytes.charCodeAt(0) === 0x52 &&
    bytes.charCodeAt(1) === 0x49 &&
    bytes.charCodeAt(2) === 0x46 &&
    bytes.charCodeAt(3) === 0x46
  ) {
    if (bytes.indexOf("WEBP") !== -1) {
      return "image/webp";
    }
  }

  // PDF: 25 50 44 46 (%PDF)
  if (
    bytes.charCodeAt(0) === 0x25 &&
    bytes.charCodeAt(1) === 0x50 &&
    bytes.charCodeAt(2) === 0x44 &&
    bytes.charCodeAt(3) === 0x46
  ) {
    return "application/pdf";
  }

  return undefined;
};

// Extracted from AI SDK's FileData type
type AISDKDataContent = string | Uint8Array | ArrayBuffer | Buffer;
type AISDKProviderReference = { [provider: string]: string } & { type?: never };

// TODO: add support for AI SDK FileData
type AISDKFileData =
  | { type: "data"; data: AISDKDataContent }
  | { type: "url"; url: URL }
  | { type: "reference"; reference: AISDKProviderReference }
  | { type: "text"; text: string };

function _isAISDKFileData(input: unknown): input is AISDKFileData {
  if (!isRecord(input)) return false;
  if (input.type === "data" && "data" in input) return true;
  if (input.type === "url" && "url" in input) return true;
  if (input.type === "reference" && "reference" in input) return true;
  if (input.type === "text" && "text" in input) return true;
  return false;
}

function _toUint8Array(fileData: unknown): Uint8Array | undefined {
  // Covers `fileData: ArrayBuffer | Buffer | Uint8Array`
  if (fileData instanceof Uint8Array) {
    return fileData;
  }

  if (
    fileData != null &&
    typeof fileData === "object" &&
    "type" in fileData &&
    "data" in fileData &&
    typeof fileData.data === "object" &&
    // eslint-disable-next-line no-instanceof/no-instanceof
    fileData.data instanceof Uint8Array
  ) {
    return fileData.data;
    // eslint-disable-next-line no-instanceof/no-instanceof
  }

  if (fileData instanceof ArrayBuffer) {
    return new Uint8Array(fileData);
  }

  return undefined;
}

export const normalizeFileDataAsDataURL = (
  fileData:
    | AISDKFileData
    | AISDKDataContent
    | LanguageModelV2DataContent
    | AISDKProviderReference
    | URL,
  mimeType: string | undefined,
): string => {
  if (_isAISDKFileData(fileData)) {
    if (fileData.type === "data") {
      return normalizeFileDataAsDataURL(fileData.data, mimeType);
    }

    if (fileData.type === "url") {
      return fileData.url.toString();
    }

    if (fileData.type === "reference") {
      // TODO: figure out if we can store the reference in a more reasonable format
      return `data:application/octet-stream;base64,${btoa(JSON.stringify(fileData.reference))}`;
    }

    if (fileData.type === "text") {
      return `data:text/plain;base64,${btoa(fileData.text)}`;
    }

    throw new Error("AISDKFileData is not supported");
  }

  if (fileData instanceof URL) {
    return fileData.toString();
  }

  if (typeof fileData !== "string") {
    const uint8Array = _toUint8Array(fileData);
    if (uint8Array) {
      let binary = "";
      for (let i = 0; i < uint8Array.length; i++) {
        binary += String.fromCharCode(uint8Array[i]);
      }
      const base64 = btoa(binary);
      const dataType =
        mimeType ??
        guessMimetypeFromBase64(base64) ??
        "application/octet-stream";

      return `data:${dataType};base64,${base64}`;
    }
  }

  if (typeof fileData === "string") {
    if (fileData.startsWith("http://") || fileData.startsWith("https://")) {
      return fileData;
    }

    if (!fileData.startsWith("data:")) {
      return `data:${
        mimeType ??
        guessMimetypeFromBase64(fileData) ??
        "application/octet-stream"
      };base64,${fileData}`;
    }

    return fileData;
  }

  return "";
};

export const convertMessageToTracedFormat = (
  rawMessage: Record<string, unknown>,
  responseMetadata?: Record<string, unknown>,
) => {
  const message = rawMessage as ModelMessage;
  const formattedMessage: Record<string, unknown> = {
    ...message,
  };
  if (Array.isArray(message.content)) {
    if (message.role === "assistant") {
      const toolCallBlocks = message.content.filter(
        (block): block is ToolCallPart => {
          return (
            block != null &&
            typeof block === "object" &&
            block.type === "tool-call"
          );
        },
      ) as ToolCallPart[];
      const toolCalls = toolCallBlocks.map((block) => {
        // AI SDK 4 shim
        let toolArgs =
          block.input ?? (("args" in block && block.args) || undefined);
        if (typeof toolArgs !== "string") {
          toolArgs = JSON.stringify(toolArgs);
        }
        return {
          id: block.toolCallId,
          type: "function",
          function: {
            name: block.toolName,
            arguments: toolArgs,
          },
        };
      });
      if (toolCalls.length > 0) {
        formattedMessage.tool_calls = toolCalls;
      }
    }
    const newContent = message.content.map((part) => {
      if (part.type === "file") {
        const { data, mediaType, filename, ...rest } = part;
        return {
          ...rest,
          file: {
            filename,
            file_data: normalizeFileDataAsDataURL(data, mediaType),
          },
        };
      } else if (part.type === "image") {
        const { image, mediaType, ...rest } = part;
        return {
          ...rest,
          type: "image_url",
          image_url: normalizeFileDataAsDataURL(image, mediaType),
        };
      } else if (
        part.type === "reasoning" &&
        "text" in part &&
        typeof part.text === "string"
      ) {
        return {
          type: "reasoning",
          reasoning: part.text,
        };
      }
      return part;
    });
    formattedMessage.content = newContent;
  } else if (message.content == null && "text" in message) {
    // AI SDK 4 shim
    formattedMessage.content = message.text ?? "";
    if (
      "toolCalls" in message &&
      Array.isArray(message.toolCalls) &&
      !("tool_calls" in formattedMessage)
    ) {
      formattedMessage.tool_calls = message.toolCalls.map((toolCall) => {
        return {
          id: toolCall.toolCallId,
          type: "function",
          function: { name: toolCall.toolName, arguments: toolCall.args },
        };
      });
    }
  }
  if (responseMetadata != null) {
    formattedMessage.response_metadata = responseMetadata;
  }
  return formattedMessage;
};
