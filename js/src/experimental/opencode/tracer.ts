import type { Event, FilePart, Message, Model, Part } from "@opencode-ai/sdk";
import { RunTree, type RunTreeConfig } from "../../run_trees.js";
import { Client } from "../../index.js";

type AggregateMessage = {
  info: Message | undefined;
  parts: Part[];
  complete: boolean;
  system: { model: Model; system: string[] } | undefined;
};

type AggregateSession = {
  messages: { [messageID: string]: AggregateMessage | undefined };
  traces: {
    [messageID: string]: {
      runs: AggregateMessage[];
      state: boolean | "subgraph";
    };
  };
  history: { info: Message; parts: Part[] }[] | undefined;
  pendingSystem: { model: Model; system: string[] } | undefined;
  postRunQueue: Promise<void>[];
  parentID: string | undefined;
};

type AggregatedToolPartState = {
  status: "pending" | "running" | "success" | "error";
  error?: string;
  input?: Record<string, unknown>;
  metadata?: {
    sessionId?: string;
    model?: { modelID: string; providerID: string };
    truncated?: boolean;
    [key: string]: unknown;
  };
  output?: string;
  time?: { start?: number; end?: number; compacted?: number };
  attachments?: FilePart[];
};

const dedupeParts = (parts: Part[]): Part[] => {
  const partById: { [partId: string]: Part } = {};
  for (const part of parts) {
    partById[part.id] = { ...partById[part.id], ...part } as Part;
  }

  return Object.values(partById);
};

const convertToStandardContentBlock = (part: Part): unknown => {
  // Ignore AI SDK specific parts
  if (part.type === "step-start" || part.type === "step-finish") {
    return [];
  }

  if (part.type === "text") {
    return {
      type: "text",
      text: part.text,
      extras: part.metadata,
    };
  }

  if (part.type === "reasoning") {
    return {
      type: "thinking",
      thinking: part.text,
    };
  }

  if (part.type === "file") {
    return {
      type: "file",
      id: part.filename ?? part.id,
      url: part.url,
      mime_type: part.mime,
    };
  }

  if (part.type === "tool") {
    return {
      type: "tool_use",
      name: part.tool,
      input: part.state.input,
      id: part.callID,
    };
  }

  if (part.type === "compaction") {
    return {
      type: "compaction",
      data: { auto: part.auto },
    };
  }

  return {
    type: "non_standard",
    value: part,
  };
};

const convertToStandardMessages = (
  messages: { info: Message | undefined; parts: Part[] }[]
): unknown[] => {
  return messages.flatMap((message) => {
    const parts = dedupeParts(message.parts);

    if (message.info?.role === "assistant") {
      // split out into "model message"
      return [
        {
          role: "assistant",
          content: parts.flatMap(convertToStandardContentBlock),
        },

        ...parts.flatMap((part) => {
          if (part.type !== "tool") return [];
          if (part.state.status === "completed") {
            return {
              role: "tool",
              content: part.state.output,
              name: part.tool,
              id: part.id,
              tool_call_id: part.callID,
            };
          }

          if (part.state.status === "error") {
            return {
              role: "tool",
              content: part.state.error,
              name: part.tool,
              id: part.id,
              tool_call_id: part.callID,
            };
          }

          return [];
        }),
      ];
    }

    if (message.info?.role === "user") {
      return {
        role: "user",
        content: parts.flatMap(convertToStandardContentBlock),
      };
    }

    return [];
  });
};

export class OpenCodeSessionTracer {
  private sessions: { [sessionID: string]: AggregateSession } = {};
  private client: Client;
  private inputConfig: Partial<RunTreeConfig>;

  constructor(inputConfig?: Partial<RunTreeConfig>) {
    this.inputConfig = inputConfig ?? {};
    this.client = inputConfig?.client ?? new Client();
  }

  private getSession(sessionID: string): AggregateSession {
    this.sessions[sessionID] ??= {
      messages: {},
      traces: {},
      history: undefined,
      pendingSystem: undefined,
      postRunQueue: [],
      parentID: undefined,
    };
    return this.sessions[sessionID];
  }

  private getMessage(sessionID: string, messageID: string): AggregateMessage {
    const session = this.getSession(sessionID);
    session.messages[messageID] ??= {
      info: undefined,
      parts: [],
      complete: false,
      system: undefined,
    };

    // Attach pending system to assistant messages
    if (
      session.pendingSystem != null &&
      session.messages[messageID]?.info?.role === "assistant"
    ) {
      session.messages[messageID].system = session.pendingSystem;
      session.pendingSystem = undefined;
    }

    return session.messages[messageID];
  }

  private getProviderMetadata(run: AggregateMessage): Record<string, unknown> {
    const info = run.info;
    if (!info || info.role !== "assistant") return {};

    const model = run.system?.model;
    const modelId = model?.id ?? info.modelID;
    const providerId = model?.providerID ?? info.providerID;
    const ls_invocation_params: Record<string, unknown> = {
      model: modelId,
      providerID: providerId,
    };
    if (model?.name) ls_invocation_params.model_display_name = model.name;
    if (model?.api?.id) ls_invocation_params.api_model_id = model.api.id;
    if (model?.api?.url) ls_invocation_params.api_url = model.api.url;
    if (model?.api?.npm) ls_invocation_params.api_npm_package = model.api.npm;

    const stepFinish = run.parts.find((part) => part.type === "step-finish");

    return {
      ls_model_name: modelId,
      ls_provider: providerId,
      ls_model_type: "chat",
      ls_invocation_params,

      usage_metadata: stepFinish
        ? {
            input_tokens: stepFinish.tokens.input,
            output_tokens:
              stepFinish.tokens.output + stepFinish.tokens.reasoning,
            total_tokens:
              stepFinish.tokens.input +
              stepFinish.tokens.output +
              stepFinish.tokens.reasoning,
            input_token_details: {
              cache_read: stepFinish.tokens.cache.read,
              cache_creation: stepFinish.tokens.cache.write,
            },
          }
        : undefined,
    };
  }

  private async sendTrace(
    sessionID: string,
    runs: AggregateMessage[],
    options?: { parentRunTree?: RunTree }
  ) {
    const session = this.getSession(sessionID);

    const userRunIdx = runs.findIndex(({ info }) => info?.role === "user");
    const userRun = runs.at(userRunIdx);
    const agentRuns = runs.slice(userRunIdx + 1);
    if (userRunIdx === -1 || userRun == null) return;

    const parentStartTime = userRun?.info?.time?.created ?? Date.now();
    const parentEndTime = agentRuns
      .flatMap((run) => run.parts)
      .reduce((acc, part) => {
        if (!("time" in part) || part.time == null) return acc;
        if (!("end" in part.time) || typeof part.time.end !== "number")
          return acc;
        return Math.max(acc, part.time.end);
      }, parentStartTime);

    if (userRun?.info) {
      session.history ??= [];
      session.history.push({ info: userRun.info, parts: userRun.parts });
    }

    const parentConfig: RunTreeConfig = {
      name: "opencode.session",
      run_type: "chain",
      start_time: parentStartTime,
      end_time: parentEndTime,
      extra: {
        metadata: {
          ls_integration: "opencode-js",
          ls_agent_type: "root",
          thread_id: sessionID,
        },
      },
      inputs: { messages: convertToStandardMessages([userRun]) },
      outputs: { messages: convertToStandardMessages(agentRuns) },
      ...this.inputConfig,
      client: this.client,
    };

    const parent =
      options?.parentRunTree?.createChild(parentConfig) ??
      new RunTree(parentConfig);
    session.postRunQueue.push(parent.postRun());

    for (const run of agentRuns) {
      const startTime = run.info?.time?.created ?? Date.now();
      const endTime = run.parts.reduce((acc, part) => {
        if (!("time" in part) || part.time == null) return acc;
        if (!("end" in part.time) || typeof part.time.end !== "number")
          return acc;
        return Math.max(acc, part.time.end);
      }, startTime);

      const parts = dedupeParts(run.parts);

      // Create child runs for tool parts
      const child = parent.createChild({
        name: "opencode.assistant.turn",
        run_type: "llm",
        start_time: startTime,
        end_time: endTime,
        inputs: {
          messages: [
            ...(run.system?.system
              ? [{ role: "system", content: run.system.system.join("\n") }]
              : []),
            ...convertToStandardMessages(session.history ?? []),
          ],
        },
        outputs: { messages: convertToStandardMessages([run]) },
        extra: { metadata: this.getProviderMetadata(run) },
      });
      session.postRunQueue.push(child.postRun());

      for (const toolPart of parts) {
        if (toolPart.type !== "tool") continue;
        const state = toolPart.state as AggregatedToolPartState;

        // Try looking for subgraph
        let toolHandled = false;
        if (state.metadata?.sessionId) {
          const session = this.getSession(state.metadata.sessionId);

          for (const trace of Object.values(session.traces)) {
            if (trace.state !== "subgraph") continue;
            await this.sendTrace(state.metadata.sessionId, trace.runs, {
              parentRunTree: child,
            });
            toolHandled = true;
          }
        }

        if (toolHandled) continue;
        const tool = child.createChild({
          name: toolPart.tool,
          run_type: "tool",
          inputs: state.input ?? {},
          outputs: {
            output: state.output,
            attachments:
              state.attachments?.map(convertToStandardContentBlock) ??
              undefined,
          },
          start_time: state.time?.start ?? startTime,
          end_time: state.time?.end ?? endTime,
          error: state.error,
          extra: { metadata: state.metadata },
        });

        session.postRunQueue.push(tool.postRun());
      }

      if (run.info) {
        session.history ??= [];
        session.history.push({ info: run.info, parts });
      }
    }
  }

  public async flush() {
    await Promise.all(
      Object.values(this.sessions).flatMap((session) => session.postRunQueue)
    );

    await this.client.flush();
    await this.client.awaitPendingTraceBatches();
  }

  public async handleSystem(
    input: { model: Model; sessionID?: string | undefined },
    output: { system: string[] }
  ) {
    if (!input.sessionID) return;
    const session = this.getSession(input.sessionID);
    session.pendingSystem = { model: input.model, system: output.system };
  }

  public async handleSessionLoad(
    sessionID: string,
    history: (sessionID: string) => Promise<{ info: Message; parts: Part[] }[]>
  ) {
    const session = this.getSession(sessionID);

    if (session.history) return;
    session.history = await history(sessionID);
  }

  public async handleEvent({ event: { properties, type } }: { event: Event }) {
    if (type === "server.instance.disposed") {
      await this.flush();
      return;
    }

    const sessionID =
      "sessionID" in properties && typeof properties.sessionID === "string"
        ? properties.sessionID
        : undefined;

    if (!sessionID) return;
    const session = this.getSession(sessionID);

    let updatedID: string | undefined;

    if (type === "session.created" || type === "session.updated") {
      session.parentID = properties.info.parentID;
    }

    if (type === "message.updated") {
      const message = this.getMessage(sessionID, properties.info.id);

      message.info = properties.info;
      updatedID = properties.info.id;
    }

    if (type === "message.part.updated") {
      const message = this.getMessage(sessionID, properties.part.messageID);

      message.parts.push(properties.part);
      updatedID = properties.part.messageID;
    }

    if (type === "message.part.removed") {
      const message = this.getMessage(sessionID, properties.messageID);

      message.parts = message.parts.filter(
        (part) => part.id !== properties.partID
      );
      updatedID = properties.messageID;
    }

    if (type === "message.removed") {
      const session = this.getSession(sessionID);
      delete session.messages[properties.messageID];
    }

    // Message consolidation logic
    const message = updatedID ? session.messages[updatedID] : undefined;
    if (message?.info?.role == null) return;

    // Skip if message is already marked as complete
    if (message.complete) return;

    message.complete =
      (message.info?.role === "user" && message.parts.length > 0) ||
      (message.info?.role === "assistant" &&
        message.parts.some((part) => part.type === "step-finish"));

    // Now we're complete, add to a trace
    if (message.complete) {
      const traceId =
        message.info.role === "user" ? message.info.id : message.info.parentID;

      session.traces[traceId] ??= { runs: [], state: false };
      const trace = session.traces[traceId];

      trace.runs.push(message);

      // Skip if trace is already marked as complete
      if (trace.state !== false) return;

      trace.state = trace.runs.some((run) =>
        run.parts.some(
          // trace is marked complete when there's a step-finish part with reason "stop"
          (part) => part.type === "step-finish" && part.reason === "stop"
        )
      );

      if (trace.state) {
        // If trace is part of a subagent call, mark it as a subgraph and submit
        // when parent is being submitted (to preserve correct dotted order)
        if (session.parentID) {
          trace.state = "subgraph";
          return;
        }

        await this.sendTrace(sessionID, trace.runs);
      }
    }
  }
}
