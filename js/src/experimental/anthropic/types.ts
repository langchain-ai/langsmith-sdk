/* eslint-disable @typescript-eslint/no-explicit-any */

// export type {
//   SDKUserMessage,
//   SDKResultMessage,
//   SDKMessage,
//   ModelUsage,
//   Options as QueryOptions,
// } from "@anthropic-ai/claude-agent-sdk";

// import type Anthropic from "@anthropic-ai/sdk";
// export type BetaContentBlock = Anthropic.Beta.BetaContentBlock;
// export type BetaToolUseBlock = Anthropic.Beta.BetaToolUseBlock;

// Mock types to avoid importing the actual types when consuming
// Use actual types above when developing
export type SDKAssistantMessage = {
  type: "assistant";
  message: {
    id: string;
    role?: string;
    content: Record<string, any>[];
    usage?: Record<string, any>;
    model?: string;
  };
  parent_tool_use_id: string | null;
};
export type SDKSystemMessage = {
  type: "system";
};

export type SDKUserMessage = {
  type: "user";
  message: {
    role?: string;
    content: Record<string, any> | Record<string, any>[] | string;
    usage?: Record<string, any>;
    model?: string;
  };
  session_id: string;
  tool_use_result?: unknown;
  parent_tool_use_id: string | null;
};
export type SDKResultMessage = {
  type: "result";
  modelUsage: ModelUsage;
  total_cost_usd: number | null;
  is_error: boolean | null;
  num_turns: number | null;
  session_id: string | null;
  duration_ms: number | null;
  duration_api_ms: number | null;
  usage: Record<string, any>;
};
export type SDKMessage =
  | SDKAssistantMessage
  | SDKUserMessage
  | SDKSystemMessage
  | SDKResultMessage;
export type ModelUsage = { [key: string]: any };
export type QueryOptions = { [key: string]: any };

export type BetaContentBlock = { [key: string]: any };
export type BetaToolUseBlock = { [key: string]: any };
