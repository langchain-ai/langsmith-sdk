import type { RunTreeConfig } from "../index.js";
import { getCurrentRunTree } from "../traceable.js";
import { KVMap } from "../schemas.js";
import { RunTree } from "../run_trees.js";
import { createUsageMetadata } from "./anthropic.js";
import type {
  BetaManagedAgentsStreamSessionEvents,
  BetaManagedAgentsSession,
} from "@anthropic-ai/sdk/resources/beta/sessions/index.mjs";

type OnlyType<TType extends BetaManagedAgentsStreamSessionEvents["type"]> =
  BetaManagedAgentsStreamSessionEvents extends infer TEvent
    ? TEvent extends { type: TType }
      ? TEvent
      : never
    : never;

function processManagedAgentStreamInputs(inputs: KVMap): KVMap {
  const args = Array.isArray(inputs.args) ? inputs.args : [];
  const [sessionID, params, requestOptions] =
    args.length > 0 ? args : [inputs.input, undefined, undefined];
  return {
    session_id: sessionID,
    ...(params ? { stream_params: params } : {}),
    ...(requestOptions ? { request_options: requestOptions } : {}),
  };
}

function getManagedAgentText(content: unknown): string {
  if (!Array.isArray(content)) return "";
  return content
    .map((block) => {
      if (
        typeof block === "object" &&
        block != null &&
        "type" in block &&
        block.type === "text" &&
        "text" in block &&
        typeof block.text === "string"
      ) {
        return block.text;
      }
      return "";
    })
    .join("");
}

function managedAgentSessionEventsAggregator(
  chunks: BetaManagedAgentsStreamSessionEvents[],
): KVMap {
  const messages: KVMap[] = [];
  const toolCalls: KVMap[] = [];
  const toolResults: KVMap[] = [];
  const errors: KVMap[] = [];
  const modelRequests: KVMap[] = [];
  const previews = new Map<string, Map<number, string>>();

  let status: string | undefined;
  let stopReason: unknown;
  const usage = {
    input_tokens: 0,
    output_tokens: 0,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0,
  };

  for (const event of chunks) {
    switch (event.type) {
      case "agent.message": {
        event.content;
        messages.push({
          id: event.id,
          role: "assistant",
          content: contentBlocksToChatContent(event.content),
          processed_at: event.processed_at,
        });
        if (typeof event.id === "string") previews.delete(event.id);
        break;
      }
      case "agent.tool_use":
      case "agent.mcp_tool_use":
      case "agent.custom_tool_use": {
        toolCalls.push({ ...event });
        break;
      }
      case "agent.tool_result":
      case "agent.mcp_tool_result": {
        toolResults.push({ ...event });
        break;
      }
      case "span.model_request_end": {
        const modelUsage = event.model_usage;
        if (modelUsage) {
          for (const key of Object.keys(usage) as Array<keyof typeof usage>) {
            const value = modelUsage[key];
            if (typeof value === "number") usage[key] += value;
          }
          modelRequests.push({
            id: event.id,
            is_error: event.is_error,
            model_request_start_id: event.model_request_start_id,
            model_usage: modelUsage,
            processed_at: event.processed_at,
          });
        }
        previews.clear();
        break;
      }
      case "session.error":
        errors.push({ ...event });
        break;
      case "session.status_running":
      case "session.status_idle":
      case "session.status_rescheduled":
      case "session.status_terminated":
        status = event.type;
        if (event.type === "session.status_idle") {
          stopReason = event.stop_reason;
        }
        break;
      case "agent.thinking":
      case "agent.thread_context_compacted":
      case "agent.thread_message_received":
      case "agent.thread_message_sent":
      case "session.deleted":
      case "session.thread_created":
      case "session.thread_status_idle":
      case "session.thread_status_running":
      case "session.thread_status_terminated":
      case "session.thread_status_rescheduled":
      case "span.model_request_start":
      case "session.updated":
      case "span.outcome_evaluation_start":
      case "span.outcome_evaluation_ongoing":
      case "span.outcome_evaluation_end":
      case "user.custom_tool_result":
      case "user.define_outcome":
      case "user.interrupt":
      case "user.message":
      case "user.tool_confirmation":
      case "user.tool_result":
        break;
    }
  }

  const unreconciledPreviews = [...previews.entries()].map(
    ([eventID, byIndex]) => ({
      id: eventID,
      text: [...byIndex.entries()]
        .sort(([left], [right]) => left - right)
        .map(([, text]) => text)
        .join(""),
    }),
  );
  const messageEvents = chunks.filter(
    (event) => event.type === "agent.message",
  );
  return {
    content: messageEvents.flatMap((message) =>
      Array.isArray(message.content) ? message.content : [],
    ),
    messages: getManagedAgentAssistantOutputMessages(chunks),
    tool_calls: toolCalls,
    tool_results: toolResults,
    errors,
    model_requests: modelRequests,
    status,
    stop_reason: stopReason,
    events: chunks,
    ...(unreconciledPreviews.length > 0
      ? { unreconciled_previews: unreconciledPreviews }
      : {}),
  };
}

function getManagedAgentInputEvents(
  chunks: BetaManagedAgentsStreamSessionEvents[],
): BetaManagedAgentsStreamSessionEvents[] {
  return chunks
    .filter(
      (event) =>
        typeof event.type === "string" &&
        (event.type.startsWith("user.") || event.type.startsWith("system.")),
    )
    .map((event) => ({ ...event }));
}

function contentBlocksToChatContent(content: unknown): unknown {
  if (!Array.isArray(content)) return content;
  const text = getManagedAgentText(content);
  return text.length > 0 &&
    content.every((block) => {
      return (
        typeof block === "object" &&
        block != null &&
        "type" in block &&
        block.type === "text"
      );
    })
    ? text
    : content;
}

function managedAgentToolUseToContentBlock(
  event: OnlyType<
    "agent.tool_use" | "agent.mcp_tool_use" | "agent.custom_tool_use"
  >,
): KVMap {
  return {
    type: "tool_use",
    id: event.id,
    name: event.name,
    input: event.input,
    ...(event.type === "agent.mcp_tool_use"
      ? { mcp_server_name: event.mcp_server_name }
      : {}),
  };
}

function getManagedAgentChatMessages(
  events: BetaManagedAgentsStreamSessionEvents[],
): KVMap[] {
  const messages: KVMap[] = [];
  for (const event of events) {
    switch (event.type) {
      case "user.message":
        messages.push({
          role: "user",
          content: contentBlocksToChatContent(event.content),
        });
        break;
      case "agent.message":
        messages.push({
          role: "assistant",
          content: contentBlocksToChatContent(event.content),
        });
        break;
      case "agent.tool_use":
      case "agent.mcp_tool_use":
      case "agent.custom_tool_use":
        messages.push({
          role: "assistant",
          content: [managedAgentToolUseToContentBlock(event)],
        });
        break;
      case "agent.tool_result":
        messages.push({
          role: "tool",
          tool_call_id: event.tool_use_id,
          content: event.content,
          ...(event.is_error != null ? { is_error: event.is_error } : {}),
        });
        break;
      case "agent.mcp_tool_result":
        messages.push({
          role: "tool",
          tool_call_id: event.mcp_tool_use_id,
          content: event.content,
          ...(event.is_error != null ? { is_error: event.is_error } : {}),
        });
        break;
      case "user.custom_tool_result":
        messages.push({
          role: "tool",
          tool_call_id: event.custom_tool_use_id,
          content: event.content,
          ...(event.is_error != null ? { is_error: event.is_error } : {}),
        });
        break;
    }
  }
  return messages;
}

function getManagedAgentAssistantOutputMessages(
  events: BetaManagedAgentsStreamSessionEvents[],
): KVMap[] {
  return events.flatMap((event) => {
    if (event.type === "agent.message") {
      return [
        {
          id: event.id,
          role: "assistant",
          content: contentBlocksToChatContent(event.content),
          processed_at: event.processed_at,
        },
      ];
    }
    if (
      event.type === "agent.tool_use" ||
      event.type === "agent.mcp_tool_use" ||
      event.type === "agent.custom_tool_use"
    ) {
      return [
        {
          id: event.id,
          role: "assistant",
          content: [managedAgentToolUseToContentBlock(event)],
          processed_at: event.processed_at,
        },
      ];
    }
    return [];
  });
}

function getManagedAgentStreamError(
  chunks: BetaManagedAgentsStreamSessionEvents[],
): string | undefined {
  const errorEvent = chunks.find((event) => event.type === "session.error");
  const error = errorEvent?.error;
  if (typeof error === "object" && error != null && "message" in error) {
    return String(error.message);
  }
  return undefined;
}

function stripLangSmithExtraFromRequestOptions<T>(options: T): T {
  if (
    typeof options === "object" &&
    options != null &&
    "langsmithExtra" in options
  ) {
    const { langsmithExtra: _langsmithExtra, ...rest } = options;
    return rest as T;
  }
  return options;
}

function getProcessedAtMillis(
  event: BetaManagedAgentsStreamSessionEvents,
): number | undefined {
  return typeof event.processed_at === "string"
    ? Date.parse(event.processed_at)
    : undefined;
}

async function postCompletedChildRun(
  childRun: RunTree,
  outputs: KVMap,
  error?: string,
  endTime?: number,
): Promise<void> {
  await childRun.end(outputs, error, endTime);
  await childRun.postRun();
}

async function createManagedAgentChildRuns(
  parentRun: RunTree,
  chunks: BetaManagedAgentsStreamSessionEvents[],
  metadata: KVMap,
  modelConfig?: KVMap,
): Promise<void> {
  const modelName =
    typeof modelConfig?.id === "string" ? modelConfig.id : undefined;
  const modelRequestStarts = new Map<
    string,
    BetaManagedAgentsStreamSessionEvents
  >();
  const childSpecs: Array<{
    startTime: number;
    index: number;
    createAndPost: () => Promise<void>;
  }> = [];

  const toolUseEvents = new Map<
    string,
    OnlyType<"agent.tool_use" | "agent.mcp_tool_use" | "agent.custom_tool_use">
  >();
  const toolResultEvents = new Map<
    string,
    OnlyType<
      "agent.tool_result" | "agent.mcp_tool_result" | "user.custom_tool_result"
    >
  >();

  for (const event of chunks) {
    if (
      event.type === "span.model_request_start" &&
      typeof event.id === "string"
    ) {
      modelRequestStarts.set(event.id, event);
    } else if (event.type === "span.model_request_end") {
      const startID =
        typeof event.model_request_start_id === "string"
          ? event.model_request_start_id
          : undefined;

      const startEvent = startID ? modelRequestStarts.get(startID) : undefined;
      const startIndex = startEvent ? chunks.indexOf(startEvent) : -1;
      const endIndex = chunks.indexOf(event);
      const eventsBeforeRequest =
        startIndex >= 0 ? chunks.slice(0, startIndex) : [];
      const eventsInRequest =
        startIndex >= 0 && endIndex >= startIndex
          ? chunks.slice(startIndex, endIndex + 1)
          : [event];
      const messageEvents = eventsInRequest.filter(
        (candidate) => candidate.type === "agent.message",
      );
      const messages = getManagedAgentAssistantOutputMessages(eventsInRequest);
      const toolCalls = eventsInRequest.filter(
        (candidate) =>
          candidate.type === "agent.tool_use" ||
          candidate.type === "agent.mcp_tool_use" ||
          candidate.type === "agent.custom_tool_use",
      );
      const content = messageEvents.flatMap((message) =>
        Array.isArray(message.content) ? message.content : [],
      );

      const usageMetadata = createUsageMetadata(event.model_usage);
      const startTime = startEvent
        ? (getProcessedAtMillis(startEvent) ?? Date.now())
        : Date.now();
      childSpecs.push({
        startTime,
        index: startIndex >= 0 ? startIndex : endIndex,
        createAndPost: async () => {
          const childRun = parentRun.createChild({
            name: "ClaudeManagedAgentModelRequest",
            run_type: "llm",
            inputs: {
              events: eventsBeforeRequest,
              messages: getManagedAgentChatMessages(eventsBeforeRequest),
              ...(startEvent ? { model_request_start: startEvent } : {}),
            },
            metadata: {
              ...metadata,
              ...(modelName ? { ls_model_name: modelName } : {}),
              ...(modelConfig
                ? {
                    ls_invocation_params: {
                      ...((metadata.ls_invocation_params as
                        | KVMap
                        | undefined) ?? {}),
                      model_config: modelConfig,
                    },
                  }
                : {}),
              ...(usageMetadata ? { usage_metadata: usageMetadata } : {}),
            },
            start_time: startTime,
          });
          await postCompletedChildRun(
            childRun,
            {
              content,
              messages,
              tool_calls: toolCalls,
              model_request_end: event,
              ...(event.model_usage ? { model_usage: event.model_usage } : {}),
              ...(usageMetadata ? { usage_metadata: usageMetadata } : {}),
            },
            event.is_error ? "Model request failed" : undefined,
            getProcessedAtMillis(event),
          );
        },
      });
    } else if (
      (event.type === "agent.tool_use" ||
        event.type === "agent.mcp_tool_use" ||
        event.type === "agent.custom_tool_use") &&
      typeof event.id === "string"
    ) {
      toolUseEvents.set(event.id, event);
    } else if (
      event.type === "agent.tool_result" &&
      typeof event.tool_use_id === "string"
    ) {
      toolResultEvents.set(event.tool_use_id, event);
    } else if (
      event.type === "agent.mcp_tool_result" &&
      typeof event.mcp_tool_use_id === "string"
    ) {
      toolResultEvents.set(event.mcp_tool_use_id, event);
    } else if (
      event.type === "user.custom_tool_result" &&
      typeof event.custom_tool_use_id === "string"
    ) {
      toolResultEvents.set(event.custom_tool_use_id, event);
    }
  }

  for (const [toolUseID, toolUse] of toolUseEvents.entries()) {
    const result = toolResultEvents.get(toolUseID);
    const toolName =
      typeof toolUse.name === "string" ? toolUse.name : "ManagedAgentTool";
    const startTime = getProcessedAtMillis(toolUse) ?? Date.now();
    childSpecs.push({
      startTime,
      index: chunks.indexOf(toolUse),
      createAndPost: async () => {
        const childRun = parentRun.createChild({
          name: toolName,
          run_type: "tool",
          inputs: {
            id: toolUseID,
            name: toolUse.name,
            input: toolUse.input,
            event: toolUse,
          },
          metadata,
          start_time: startTime,
        });
        await postCompletedChildRun(
          childRun,
          result ? { event: result, content: result.content } : {},
          result?.is_error ? "Tool execution failed" : undefined,
          result ? getProcessedAtMillis(result) : undefined,
        );
      },
    });
  }

  childSpecs.sort(
    (left, right) =>
      left.startTime - right.startTime || left.index - right.index,
  );
  for (const childSpec of childSpecs) {
    await childSpec.createAndPost();
  }
}

export function wrapManagedAgentSessionEvents({
  originalBeta,
  tracedBeta,
  cleanedOptions,
  prepopulatedInvocationParams,
}: {
  originalBeta: any;
  tracedBeta: any;
  cleanedOptions: Partial<RunTreeConfig>;
  prepopulatedInvocationParams: unknown;
}): void {
  const createManagedAgentStreamRun = (
    sessionID: string,
    params?: KVMap,
    requestOptions?: { langsmithExtra?: Partial<RunTreeConfig> },
  ) => {
    const runtimeConfig = requestOptions?.langsmithExtra ?? {};
    const parentRun = getCurrentRunTree(true);
    const runConfig: RunTreeConfig = {
      ...cleanedOptions,
      ...runtimeConfig,
      name: runtimeConfig.name ?? cleanedOptions.name ?? "ClaudeManagedAgent",
      run_type: "chain",
      inputs: { session_id: sessionID },
      tags: [
        ...new Set([
          ...(cleanedOptions.tags ?? []),
          ...(runtimeConfig.tags ?? []),
        ]),
      ],
      metadata: {
        ...cleanedOptions.metadata,
        ...runtimeConfig.metadata,
        ls_provider: "anthropic",
        ls_model_type: "chat",
        thread_id: sessionID,
        ls_invocation_params: {
          ...(typeof prepopulatedInvocationParams === "object" &&
          prepopulatedInvocationParams != null
            ? prepopulatedInvocationParams
            : {}),
          session_id: sessionID,
          ...(params ?? {}),
        },
      },
    };
    return parentRun
      ? parentRun.createChild(runConfig)
      : new RunTree(runConfig);
  };

  // Wrap Claude Managed Agents session event methods if they exist.
  if (originalBeta.sessions?.events) {
    tracedBeta.sessions = Object.create(
      Object.getPrototypeOf(tracedBeta.sessions),
    );
    Object.assign(tracedBeta.sessions, originalBeta.sessions);

    tracedBeta.sessions.events = Object.create(
      Object.getPrototypeOf(tracedBeta.sessions.events),
    );
    Object.assign(tracedBeta.sessions.events, originalBeta.sessions.events);

    if (typeof originalBeta.sessions.events.stream === "function") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const streamManagedAgentEvents = async function (...args: any[]) {
        const [sessionID, params, requestOptions] = args as [
          string,
          KVMap | undefined,
          ({ langsmithExtra?: Partial<RunTreeConfig> } & Record<
            string,
            unknown
          >)?,
        ];
        const sanitizedArgs = [...args];
        sanitizedArgs[2] = stripLangSmithExtraFromRequestOptions(
          sanitizedArgs[2],
        );
        while (
          sanitizedArgs.length > 1 &&
          sanitizedArgs[sanitizedArgs.length - 1] === undefined
        ) {
          sanitizedArgs.pop();
        }

        const runTree = createManagedAgentStreamRun(
          sessionID,
          params,
          requestOptions,
        );

        const sessionPromise: Promise<BetaManagedAgentsSession | undefined> =
          originalBeta.sessions?.retrieve
            ? originalBeta.sessions.retrieve
                .bind(originalBeta.sessions)(sessionID)
                .catch(() => undefined)
            : Promise.resolve(undefined);

        const stream = await originalBeta.sessions?.events?.stream.bind(
          originalBeta.sessions.events,
        )(...sanitizedArgs);

        const iterator: AsyncIterator<BetaManagedAgentsStreamSessionEvents> =
          stream[Symbol.asyncIterator]();

        const chunks: BetaManagedAgentsStreamSessionEvents[] = [];
        let finalized = false;

        const finalize = async (error?: string) => {
          if (finalized) return;
          finalized = true;
          const outputs = managedAgentSessionEventsAggregator(chunks);
          const inputEvents = getManagedAgentInputEvents(chunks);
          runTree.inputs = {
            ...processManagedAgentStreamInputs({
              args: [sessionID, params, sanitizedArgs[2]],
            }),
            ...(inputEvents.length > 0
              ? {
                  events: inputEvents,
                  messages: getManagedAgentChatMessages(inputEvents),
                }
              : {}),
          };
          const finalError = error ?? getManagedAgentStreamError(chunks);
          const session = await sessionPromise;

          const modelConfig =
            typeof session?.agent?.model === "object" &&
            session.agent.model != null
              ? (session.agent.model as KVMap)
              : undefined;
          await runTree.end(outputs, finalError);
          await runTree.postRun();
          await createManagedAgentChildRuns(
            runTree,
            chunks,
            runTree.extra.metadata ?? {},
            modelConfig,
          );
        };

        stream[Symbol.asyncIterator] = () => ({
          async next() {
            try {
              const result = await iterator.next();
              if (result.done) {
                await finalize();
                return result;
              }
              chunks.push(result.value);
              if (
                result.value.type === "session.status_idle" ||
                result.value.type === "session.status_terminated" ||
                result.value.type === "session.deleted" ||
                result.value.type === "session.error"
              ) {
                await finalize();
              }
              return result;
            } catch (error) {
              await finalize(String(error));
              throw error;
            }
          },
          async return(value?: unknown) {
            if (!finalized) {
              await iterator.return?.(value);
              await finalize("Cancelled");
            } else {
              await iterator.return?.(value);
            }
            return { done: true, value };
          },
          async throw(error?: unknown) {
            await finalize(String(error));
            if (iterator.throw) return iterator.throw(error);
            throw error;
          },
        });
        return stream;
      };
      Object.defineProperty(streamManagedAgentEvents, "langsmith:traceable", {
        value: { name: "ClaudeManagedAgent", run_type: "chain" },
      });
      tracedBeta.sessions.events.stream = streamManagedAgentEvents;
    }

    if (typeof originalBeta.sessions.events.send === "function") {
      // Do not trace `send` as a separate run. The API returns the submitted
      // user events, which makes the run output look like a duplicate of the
      // input. Instead, annotate the active stream run for the same session.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      tracedBeta.sessions.events.send = function sendManagedAgentEvents(
        ...args: any[]
      ) {
        const sanitizedArgs = [...args];
        if (
          typeof sanitizedArgs[2] === "object" &&
          sanitizedArgs[2] != null &&
          "langsmithExtra" in sanitizedArgs[2]
        ) {
          const { langsmithExtra: _langsmithExtra, ...rest } = sanitizedArgs[2];
          sanitizedArgs[2] = rest;
        }
        return originalBeta.sessions?.events?.send.bind(
          originalBeta.sessions.events,
        )(...sanitizedArgs);
      };
    }
  }
}
