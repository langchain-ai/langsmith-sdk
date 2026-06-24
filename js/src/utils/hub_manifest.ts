const FLAT_HUB_PROMPT_TAGS = new Set([
  "StructuredPrompt",
  "ChatPromptTemplate",
  "PromptTemplate",
]);
const WRAPPED_HUB_PROMPT_TAGS = new Set([
  "PromptPlayground",
  "RunnableSequence",
]);

function hubManifestTag(manifest: Record<string, unknown>): string | undefined {
  const id = manifest.id;
  if (!Array.isArray(id) || id.length === 0) {
    return undefined;
  }
  const tag = id[id.length - 1];
  return typeof tag === "string" ? tag : undefined;
}

function defaultHubModelManifest(): Record<string, unknown> {
  return {
    id: ["langchain", "schema", "runnable", "RunnableBinding"],
    lc: 1,
    type: "constructor",
    kwargs: {
      bound: {
        id: ["langchain", "chat_models", "openai", "ChatOpenAI"],
        lc: 1,
        type: "constructor",
        kwargs: {
          openai_api_key: {
            id: ["OPENAI_API_KEY"],
            lc: 1,
            type: "secret",
          },
        },
      },
      kwargs: {},
    },
  };
}

/** Wrap flat prompt manifests in PromptPlayground format for Hub commits. */
export function wrapManifestForHubPush<T extends Record<string, unknown>>(
  manifest: T,
): T | Record<string, unknown> {
  const tag = hubManifestTag(manifest);
  if (tag && WRAPPED_HUB_PROMPT_TAGS.has(tag)) {
    return manifest;
  }
  if (manifest.lc !== 1 || manifest.type !== "constructor") {
    return manifest;
  }
  if (!tag || !FLAT_HUB_PROMPT_TAGS.has(tag)) {
    return manifest;
  }
  return {
    lc: 1,
    type: "constructor",
    id: ["langsmith", "playground", "PromptPlayground"],
    kwargs: {
      first: manifest,
      last: defaultHubModelManifest(),
    },
  };
}
