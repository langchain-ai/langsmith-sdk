/**
 * Payload builders shared by the CodSpeed benchmarks.
 *
 * The shapes mirror what the SDK actually sees in production: chat-completion
 * style inputs/outputs, payloads dominated by a few very large strings (base64
 * attachments) and "structural" payloads made of many small strings spread over
 * a wide, nested object graph.
 */

export interface Message {
  role: string;
  content: string;
}

/** A chat-completion style payload of `messages` messages. */
export function chatPayload(messages: number): Record<string, unknown> {
  return {
    messages: Array.from({ length: messages }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: `This is message number ${i} of the conversation.`,
    })),
    metadata: {
      ls_model_name: "gpt-4o-mini",
      ls_provider: "openai",
      ls_temperature: 0.7,
    },
  };
}

/** A payload dominated by a handful of very large strings. */
export function largeStringPayload(bytes: number): Record<string, unknown> {
  const large = "a".repeat(bytes);
  return {
    name: "large-string payload",
    attachments: [{ data: large }, { data: large }],
    metadata: { created_at: "2024-10-22T19:00:00Z", version: 1 },
  };
}

/** A wide and nested payload built out of many small strings. */
export function structuralPayload(
  width: number,
  depth: number,
): Record<string, unknown> {
  const build = (level: number): Record<string, unknown> => {
    const node: Record<string, unknown> = {};
    for (let i = 0; i < width; i += 1) {
      node[`key_${level}_${i}`] =
        level >= depth ? `value ${level}-${i}` : build(level + 1);
    }
    return node;
  };
  return { input: build(0) };
}

/** A payload exercising the well-known type handling of the serializer. */
export function wellKnownTypesPayload(
  entries: number,
): Record<string, unknown> {
  return {
    map: new Map(
      Array.from({ length: entries }, (_, i) => [`key_${i}`, `value_${i}`]),
    ),
    set: new Set(Array.from({ length: entries }, (_, i) => i)),
    dates: Array.from({ length: entries }, () => new Date(0)),
    regexes: Array.from({ length: entries }, () => /test.*pattern/gi),
    errors: Array.from({ length: entries }, (_, i) => new Error(`boom ${i}`)),
  };
}
