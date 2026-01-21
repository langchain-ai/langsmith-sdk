import type Anthropic from "@anthropic-ai/sdk";

/**
 * Converts SDK content blocks into serializable objects.
 * Matches Python's flatten_content_blocks behavior.
 */
export function flattenContentBlocks(
  content: Anthropic.Beta.BetaContentBlock[] | unknown
): Array<Record<string, unknown>> | unknown {
  if (!Array.isArray(content)) {
    return content;
  }

  return content.map((block) => {
    if (!block || typeof block !== "object" || !("type" in block)) {
      return block;
    }

    const blockType = block.type;

    switch (blockType) {
      case "text":
        return { type: "text", text: block.text || "" };
      case "thinking":
        return {
          type: "thinking",
          thinking: block.thinking || "",
          signature: block.signature || "",
        };
      case "tool_use":
        return {
          type: "tool_use",
          id: block.id,
          name: block.name,
          input: block.input,
        };
      case "tool_result":
        return {
          type: "tool_result",
          tool_use_id: block.tool_use_id,
          content: block.content,
          is_error: block.is_error || false,
        };
      default:
        return block;
    }
  });
}

export function isToolResultBlock(
  block: unknown
): block is {
  type: "tool_result";
  tool_use_id: string;
  content: string;
  is_error: boolean;
} {
  if (typeof block !== "object" || block == null) return false;
  if (!("type" in block)) return false;
  return block.type === "tool_result";
}
