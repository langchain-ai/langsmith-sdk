export {
  Client,
  type ClientConfig,
  type LangSmithTracingClientInterface,
} from "./client.js";

export type {
  Dataset,
  Example,
  TracerSession,
  Run,
  Feedback,
  FeedbackConfigSchema,
  RetrieverOutput,
} from "./schemas.js";

export { RunTree, type RunTreeConfig, type WriteReplica } from "./run_trees.js";

export { overrideFetchImplementation } from "./singletons/fetch.js";

export { getDefaultProjectName } from "./utils/project.js";

export {
  computeRunIdForSecondaryReplica,
  uuid7,
  uuid7FromTime,
} from "./uuid.js";

export { isTracingEnabled } from "./utils/guard.js";

export {
  Cache,
  PromptCache,
  type CacheConfig,
  type CacheMetrics,
  configureGlobalPromptCache,
  promptCacheSingleton,
} from "./utils/prompt_cache/index.js";

export {
  LangsmithError,
  APIError,
  APIUserAbortError,
  APIConnectionError,
  APIConnectionTimeoutError,
  BadRequestError,
  AuthenticationError,
  PermissionDeniedError,
  NotFoundError,
  ConflictError,
  UnprocessableEntityError,
  RateLimitError,
  InternalServerError,
} from "./_openapi_client/core/error.js";

// Update using pnpm bump-version
export const __version__ = "0.8.5";

// Metadata key to hide a traced run from LangSmith's Messages View.
export const LS_MESSAGE_VIEW_EXCLUDE = "ls_message_view_exclude" as const;
