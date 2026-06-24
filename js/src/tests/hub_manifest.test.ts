import { describe, expect, it } from "@jest/globals";

import { wrapManifestForHubPush } from "../utils/hub_manifest.js";

const FLAT_STRUCTURED_PROMPT = {
  lc: 1,
  type: "constructor",
  id: ["langchain_core", "prompts", "structured", "StructuredPrompt"],
  kwargs: {
    input_variables: ["input"],
    messages: [],
    schema_: {
      type: "object",
      properties: { score: { type: "boolean" } },
    },
  },
};

describe("wrapManifestForHubPush", () => {
  it("wraps flat StructuredPrompt manifests", () => {
    const wrapped = wrapManifestForHubPush(FLAT_STRUCTURED_PROMPT);

    expect(wrapped.id).toEqual(["langsmith", "playground", "PromptPlayground"]);
    expect((wrapped as { kwargs: { first: unknown } }).kwargs.first).toBe(
      FLAT_STRUCTURED_PROMPT,
    );
    expect((wrapped as { kwargs: { last: { id: string[] } } }).kwargs.last.id).toEqual(
      ["langchain", "schema", "runnable", "RunnableBinding"],
    );
  });

  it.each([
    {
      id: ["langsmith", "playground", "PromptPlayground"],
      label: "PromptPlayground",
    },
    {
      id: ["langchain", "schema", "runnable", "RunnableSequence"],
      label: "RunnableSequence",
    },
  ])("leaves $label manifests unchanged", ({ id }) => {
    const manifest = {
      lc: 1,
      type: "constructor",
      id,
      kwargs: { first: { id: ["prompt"] }, last: { id: ["model"] } },
    };

    expect(wrapManifestForHubPush(manifest)).toBe(manifest);
  });
});
