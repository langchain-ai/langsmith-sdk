import { describe, expect, it } from "@jest/globals";

import {
  defaultHubModelManifest,
  wrapManifestForHubPush,
} from "../utils/hub_manifest.js";

describe("wrapManifestForHubPush", () => {
  it("wraps flat StructuredPrompt manifests", () => {
    const flat = {
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

    const wrapped = wrapManifestForHubPush(flat);

    expect(wrapped.id).toEqual(["langsmith", "playground", "PromptPlayground"]);
    expect((wrapped as { kwargs: { first: unknown } }).kwargs.first).toBe(flat);
    expect(defaultHubModelManifest().id).toEqual([
      "langchain",
      "schema",
      "runnable",
      "RunnableBinding",
    ]);
  });

  it("leaves PromptPlayground manifests unchanged", () => {
    const manifest = {
      lc: 1,
      type: "constructor",
      id: ["langsmith", "playground", "PromptPlayground"],
      kwargs: { first: { id: ["prompt"] }, last: { id: ["model"] } },
    };

    expect(wrapManifestForHubPush(manifest)).toBe(manifest);
  });

  it("leaves RunnableSequence manifests unchanged", () => {
    const manifest = {
      lc: 1,
      type: "constructor",
      id: ["langchain", "schema", "runnable", "RunnableSequence"],
      kwargs: { first: { id: ["prompt"] }, last: { id: ["model"] } },
    };

    expect(wrapManifestForHubPush(manifest)).toBe(manifest);
  });
});
