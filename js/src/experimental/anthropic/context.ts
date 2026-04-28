import type { RunTree, RunTreeConfig } from "../../run_trees.js";
import {
  convertFromAnthropicMessage,
  isTaskTool,
  isToolBlock,
  mergeMessagesById,
} from "./messages.js";
import { getCurrentRunTree } from "../../traceable.js";
import {
  aggregateUsageFromModelUsage,
  correctUsageFromResults,
  extractUsageFromMessage,
} from "./usage.js";
import { readTranscript, type TranscriptAssistantTurn } from "./transcripts.js";
import type { SDKMessage, SDKResultMessage } from "./types.js";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value != null && !Array.isArray(value);
}

function isToolResultError(value: unknown): boolean {
  return isRecord(value) && (value.is_error === true || value.isError === true);
}

function makeSubagentTranscriptPathKey(
  path: string,
  toolUseId?: string,
  agentType?: string,
): string {
  return JSON.stringify([path, toolUseId ?? null, agentType ?? null]);
}

/**
 * @internal
 */
export class StreamManager {
  private static liveManagers: Set<StreamManager> = new Set();
  private static managersByRootRun = new WeakMap<RunTree, StreamManager>();

  private rootRun?: RunTree;
  namespaces: { [namespace: string]: RunTree | undefined };
  history: { [namespace: string]: SDKMessage[] };

  assistant: { [messageId: string]: RunTree | undefined } = {};
  tools: { [toolUseId: string]: RunTree | undefined } = {};
  subagents: { [toolUseId: string]: RunTree | undefined } = {};

  mainTranscriptPath?: string;
  subagentTranscriptPaths: {
    path: string;
    toolUseId?: string;
    agentType?: string;
  }[] = [];
  private pendingAgentTools: Map<string, Record<string, unknown>> = new Map();
  private agentToToolUseId: Map<string, string> = new Map();
  private transcriptPathKeys: Set<string> = new Set();
  private resultModelUsage?: SDKResultMessage["modelUsage"];

  postRunQueue: Promise<void>[] = [];
  runTrees: RunTree[] = [];

  constructor() {
    const rootRun = getCurrentRunTree(true);
    this.rootRun = rootRun;
    this.namespaces = rootRun?.createChild ? { root: rootRun } : {};
    this.history = { root: [] };
    if (rootRun != null) {
      StreamManager.managersByRootRun.set(rootRun, this);
    }
    StreamManager.liveManagers.add(this);
  }

  dispose() {
    StreamManager.liveManagers.delete(this);
    if (this.rootRun != null) {
      StreamManager.managersByRootRun.delete(this.rootRun);
    }
  }

  async addMessage(message: SDKMessage) {
    const eventTime = Date.now();

    // Short-circuit if no root run found
    // This can happen if tracing is disabled globally
    if (this.namespaces["root"] == null) return;

    if (message.type === "result") {
      if (message.modelUsage) {
        this.resultModelUsage = message.modelUsage;
      }

      const usage = message.modelUsage
        ? aggregateUsageFromModelUsage(message.modelUsage)
        : extractUsageFromMessage(message);

      if (message.total_cost_usd != null && usage != null) {
        usage.total_cost = message.total_cost_usd;
      }

      this.namespaces["root"].extra ??= {};
      this.namespaces["root"].extra.metadata ??= {};
      this.namespaces["root"].extra.metadata.usage_metadata = usage;

      this.namespaces["root"].extra.metadata.is_error = message.is_error;
      this.namespaces["root"].extra.metadata.num_turns = message.num_turns;
      this.namespaces["root"].extra.metadata.session_id = message.session_id;
      this.namespaces["root"].extra.metadata.duration_ms = message.duration_ms;
      this.namespaces["root"].extra.metadata.duration_api_ms =
        message.duration_api_ms;
    }

    // Skip non-user / non-assistant messages
    if (!("message" in message)) return;

    const namespace = (() => {
      if ("parent_tool_use_id" in message)
        return message.parent_tool_use_id ?? "root";
      return "root";
    })();

    // `eventTime` records the time we receive an event, which for `includePartialMessages: false`
    // equals to the end time of an LLM block, so we need to use the first available end time within namespace.
    const candidateStartTime =
      this.namespaces[namespace]?.child_runs?.at(-1)?.end_time ??
      this.namespaces[namespace]?.start_time ??
      eventTime;

    this.history[namespace] ??= this.history["root"].slice();

    if (message.type === "assistant") {
      const messageId = message.message.id;

      this.assistant[messageId] ??= this.createChild(namespace, {
        name: "claude.assistant.turn",
        run_type: "llm",
        start_time: candidateStartTime,
        inputs: {
          messages: convertFromAnthropicMessage(this.history[namespace]),
        },
        outputs: { output: { messages: [] } },
      });

      if (this.assistant[messageId] == null) return;

      this.assistant[messageId].outputs = (() => {
        const prevMessages =
          this.assistant[messageId].outputs?.output.messages ?? [];
        const newMessages = convertFromAnthropicMessage([message]);
        return {
          output: {
            messages: mergeMessagesById(prevMessages, newMessages),
          },
        };
      })();

      this.assistant[messageId].end_time = eventTime;

      this.assistant[messageId].extra ??= {};
      this.assistant[messageId].extra.metadata ??= {};

      if (message.message.model != null) {
        this.assistant[messageId].extra.metadata.ls_model_name =
          message.message.model;
      }

      this.assistant[messageId].extra.metadata.usage_metadata =
        extractUsageFromMessage(message);

      const tools = Array.isArray(message.message.content)
        ? message.message.content.filter((block) => isToolBlock(block))
        : [];

      for (const block of tools) {
        if (isTaskTool(block)) {
          this.createAgentToolRun(namespace, block, eventTime);
        } else {
          this.createToolRun(namespace, block, eventTime);
        }
      }
    }

    if (message.type === "user") {
      const toolResultBlocks = Array.isArray(message.message.content)
        ? message.message.content.filter((block) => "tool_use_id" in block)
        : [];

      const getToolOutput = (result: unknown) => {
        if (isRecord(result)) {
          return result;
        }

        return { content: result };
      };

      const getToolError = (result: unknown): string => {
        if (["string", "number", "boolean"].includes(typeof result)) {
          return String(result);
        }
        if (Array.isArray(result)) {
          return result.map(getToolError).join("\n");
        }
        if (isRecord(result)) {
          if (typeof result.error === "string") return result.error;
          if (typeof result.text === "string") return result.text;
          if ("content" in result) return getToolError(result.content);
        }
        return JSON.stringify(result);
      };

      for (const block of toolResultBlocks) {
        const tool = this.tools[block.tool_use_id];
        const subagent = this.subagents[block.tool_use_id];
        if (tool != null || subagent != null) {
          // Previous versions of @anthropic-ai/claude-agent-sdk did provide
          // tool result in `message.tool_use_result`, but at least since 0.2.50 it disappeared,
          // so we rely on the last tool result block instead.
          const result =
            message.tool_use_result != null && toolResultBlocks.length === 1
              ? message.tool_use_result
              : block.content;

          const toolOutput = getToolOutput(result);

          const isError = isToolResultError(block) || isToolResultError(result);

          const toolError = isError ? getToolError(result) : undefined;

          await tool?.end(toolOutput, toolError);
          // Match Python's lifecycle: PostToolUse sets outputs on the
          // subagent chain, but the subagent itself is not ended until after
          // transcript reconciliation. Hidden transcript LLM/tool children can
          // arrive after the Agent/Task tool result, so ending the chain here
          // can make reconciled children appear outside their parent bounds.
          if (subagent != null) {
            subagent.outputs ??= toolOutput;
            subagent.error ??= toolError;
          }
        }
      }
    }

    this.history[namespace].push(message);
  }

  addHookEvent(input: unknown, toolUseId?: string) {
    if (typeof input !== "object" || input == null) return;
    const data = input as Record<string, unknown>;

    if (
      this.mainTranscriptPath == null &&
      typeof data.transcript_path === "string"
    ) {
      this.mainTranscriptPath = data.transcript_path;
    }

    if (
      data.hook_event_name === "PreToolUse" &&
      typeof toolUseId === "string" &&
      (data.tool_name === "Agent" || data.tool_name === "Task")
    ) {
      this.pendingAgentTools.set(
        toolUseId,
        typeof data.tool_input === "object" && data.tool_input != null
          ? (data.tool_input as Record<string, unknown>)
          : {},
      );
      return;
    }

    if (data.hook_event_name === "SubagentStart") {
      const agentId =
        typeof data.agent_id === "string" ? data.agent_id : undefined;
      if (agentId == null) return;

      const agentType =
        typeof data.agent_type === "string" ? data.agent_type : undefined;
      let matchedToolUseId: string | undefined;
      for (const [pendingToolUseId, toolInput] of this.pendingAgentTools) {
        const pendingAgentType =
          typeof toolInput.subagent_type === "string"
            ? toolInput.subagent_type
            : typeof toolInput.agent_type === "string"
            ? toolInput.agent_type
            : undefined;
        if (
          agentType == null ||
          pendingAgentType == null ||
          pendingAgentType === agentType
        ) {
          matchedToolUseId = pendingToolUseId;
          break;
        }
      }
      matchedToolUseId ??= this.pendingAgentTools.keys().next().value;
      if (matchedToolUseId != null) {
        this.agentToToolUseId.set(agentId, matchedToolUseId);
        this.pendingAgentTools.delete(matchedToolUseId);
      }
      return;
    }

    if (data.hook_event_name === "SubagentStop") {
      const transcriptPath =
        typeof data.agent_transcript_path === "string"
          ? data.agent_transcript_path
          : undefined;
      if (!transcriptPath) return;

      const agentId =
        typeof data.agent_id === "string" ? data.agent_id : undefined;
      const agentType =
        typeof data.agent_type === "string" ? data.agent_type : undefined;
      const mappedToolUseId =
        agentId != null ? this.agentToToolUseId.get(agentId) : undefined;
      if (agentId != null) this.agentToToolUseId.delete(agentId);

      this.addSubagentTranscriptPath(
        transcriptPath,
        mappedToolUseId,
        agentType,
      );
    }
  }

  addSubagentTranscriptPath(
    path: string,
    toolUseId?: string,
    agentType?: string,
  ) {
    const key = makeSubagentTranscriptPathKey(path, toolUseId, agentType);
    if (this.transcriptPathKeys.has(key)) return;
    this.transcriptPathKeys.add(key);
    this.subagentTranscriptPaths.push({ path, toolUseId, agentType });
  }

  static getActiveToolRun(
    toolName?: string,
    input?: unknown,
  ): RunTree | undefined {
    const currentRun = getCurrentRunTree(true);
    const currentManager =
      currentRun != null
        ? StreamManager.managersByRootRun.get(currentRun)
        : undefined;
    const currentRunTree = currentManager?.getActiveToolRun(toolName, input);
    if (currentRunTree != null) return currentRunTree;

    // Last resort: the SDK invoked an MCP handler from a detached async context
    // that did not inherit the existing LangSmith AsyncLocalStorage. Require
    // both tool name and input to match before scanning live managers to avoid
    // cross-query attribution.
    if (toolName == null || input === undefined) return undefined;

    for (const manager of Array.from(StreamManager.liveManagers).reverse()) {
      if (manager === currentManager) continue;
      const runTree = manager.getActiveToolRun(toolName, input);
      if (runTree != null) return runTree;
    }
    return undefined;
  }

  private getActiveToolRun(
    toolName?: string,
    input?: unknown,
  ): RunTree | undefined {
    const toolEntries = Object.values(this.tools).filter(
      (runTree): runTree is RunTree =>
        runTree != null && runTree.end_time == null && runTree.error == null,
    );

    return toolEntries.find((runTree) => {
      if (toolName != null) {
        const runName = String(runTree.name);
        const nameMatches =
          runName === toolName ||
          runName.includes(toolName) ||
          toolName.includes(runName);
        if (!nameMatches) return false;
      }

      if (input !== undefined) {
        const recorded = runTree.inputs?.input ?? {};
        try {
          return JSON.stringify(recorded) === JSON.stringify(input ?? {});
        } catch {
          return false;
        }
      }

      return true;
    });
  }

  protected createChild(
    namespace: string,
    args: Parameters<RunTree["createChild"]>[0],
  ): RunTree | undefined {
    const parentRunTree = this.namespaces[namespace];
    if (parentRunTree == null) return undefined;
    return this.createChildRun(parentRunTree, args);
  }

  private createChildRun(
    parentRunTree: RunTree,
    args: Parameters<RunTree["createChild"]>[0],
  ): RunTree | undefined {
    const runTree = parentRunTree.createChild(args);
    if (runTree == null) return undefined;

    this.postRunQueue.push(runTree.postRun());
    this.runTrees.push(runTree);
    return runTree;
  }

  private getAgentName(block: { input: Record<string, unknown> }): string {
    const subagentType = block.input.subagent_type;
    if (typeof subagentType === "string" && subagentType.length > 0) {
      return subagentType;
    }

    const agentType = block.input.agent_type;
    if (typeof agentType === "string" && agentType.length > 0) {
      return agentType;
    }

    const description = block.input.description;
    if (typeof description === "string" && description.length > 0) {
      return description.split(" ")[0] || "unknown-agent";
    }

    return "unknown-agent";
  }

  private createToolRun(
    namespace: string,
    block: Record<string, unknown>,
    startTime?: number,
  ): RunTree | undefined {
    if (typeof block.id !== "string") return undefined;

    const name = typeof block.name === "string" ? block.name : "unknown-tool";
    this.tools[block.id] ??=
      this.createChild(namespace, {
        name,
        run_type: "tool",
        inputs: block.input ? { input: block.input } : {},
        start_time: startTime,
      }) ?? this.tools[block.id];
    return this.tools[block.id];
  }

  private createAgentToolRun(
    namespace: string,
    block: Record<string, unknown>,
    startTime?: number,
  ) {
    if (typeof block.id !== "string") return;
    if (
      typeof block.input !== "object" ||
      block.input == null ||
      Array.isArray(block.input)
    ) {
      return;
    }

    const input = block.input as Record<string, unknown>;
    const agentToolRun = this.createToolRun(namespace, block, startTime);
    if (agentToolRun == null) return;

    this.subagents[block.id] ??=
      this.createChildRun(agentToolRun, {
        name: this.getAgentName({ input }),
        run_type: "chain",
        inputs: input,
        start_time: startTime,
        extra: {
          metadata: {
            ls_agent_type: "subagent",
          },
        },
      }) ?? this.subagents[block.id];

    this.namespaces[block.id] ??= this.subagents[block.id];
  }

  private resolveSubagentNamespace(agentType?: string): string | undefined {
    const entries = Object.entries(this.namespaces);
    if (agentType == null) return undefined;
    return entries.find(([, runTree]) => runTree?.name === agentType)?.[0];
  }

  private createSyntheticAssistantRun(
    namespace: string,
    turn: TranscriptAssistantTurn,
  ) {
    let runTree = this.assistant[turn.messageId];

    if (runTree == null) {
      runTree = this.createChild(namespace, {
        name: "claude.assistant.turn",
        run_type: "llm",
        start_time: turn.timestamp,
        inputs:
          turn.inputMessages.length > 0 ? { messages: turn.inputMessages } : {},
        outputs: {
          output: { messages: convertFromAnthropicMessage(turn.message) },
        },
        extra: {
          metadata: {
            ls_provider: "anthropic",
            ...(turn.model != null ? { ls_model_name: turn.model } : {}),
            ...(turn.usageMetadata != null
              ? { usage_metadata: turn.usageMetadata }
              : {}),
          },
        },
      });
      if (runTree == null) return;
      this.assistant[turn.messageId] = runTree;
    } else {
      runTree.outputs = {
        output: { messages: convertFromAnthropicMessage(turn.message) },
      };
      runTree.extra ??= {};
      runTree.extra.metadata ??= {};
      if (turn.model != null) runTree.extra.metadata.ls_model_name = turn.model;
      if (turn.usageMetadata != null) {
        runTree.extra.metadata.usage_metadata = turn.usageMetadata;
      }
    }

    runTree.end_time = turn.timestamp;

    const tools = Array.isArray(turn.message.message.content)
      ? turn.message.message.content.filter((block) => isToolBlock(block))
      : [];

    for (const block of tools) {
      if (isTaskTool(block)) {
        this.createAgentToolRun(namespace, block, turn.timestamp);
      } else {
        this.createToolRun(namespace, block, turn.timestamp);
      }
    }
  }

  private async reconcileTranscripts() {
    const usageByMessageId: Record<string, Record<string, unknown>> = {};

    if (this.mainTranscriptPath != null) {
      const transcript = await readTranscript(this.mainTranscriptPath);
      Object.assign(usageByMessageId, transcript.usageByMessageId);
    }

    for (const transcriptPath of this.subagentTranscriptPaths) {
      const namespace =
        transcriptPath.toolUseId ??
        this.resolveSubagentNamespace(transcriptPath.agentType);
      if (namespace == null || this.namespaces[namespace] == null) continue;

      const transcript = await readTranscript(transcriptPath.path);
      Object.assign(usageByMessageId, transcript.usageByMessageId);

      for (const turn of transcript.turns) {
        this.createSyntheticAssistantRun(namespace, turn);
      }

      for (const toolResult of transcript.toolResults) {
        const tool = this.tools[toolResult.toolUseId];
        if (tool == null) continue;
        const output = isRecord(toolResult.content)
          ? toolResult.content
          : { content: toolResult.content };
        const error = toolResult.isError
          ? typeof toolResult.content === "string" ||
            typeof toolResult.content === "number" ||
            typeof toolResult.content === "boolean"
            ? String(toolResult.content)
            : JSON.stringify(toolResult.content)
          : undefined;
        await tool.end(output, error);
      }
    }

    for (const [messageId, usage] of Object.entries(usageByMessageId)) {
      const runTree = this.assistant[messageId];
      if (runTree == null) continue;
      runTree.extra ??= {};
      runTree.extra.metadata ??= {};
      runTree.extra.metadata.usage_metadata = usage;
    }
  }

  async finish() {
    try {
      await this.reconcileTranscripts();

      if (this.resultModelUsage != null) {
        correctUsageFromResults(
          this.resultModelUsage,
          Object.values(this.assistant).filter((runTree) => runTree != null),
        );
      }

      // Clean up incomplete tools and finalise subagent calls. This mirrors the
      // Python integration: Agent/Task tool runs are ended when their tool result
      // arrives, while subagent chain runs are finalised only after transcript
      // reconciliation so hidden child LLM/tool runs are created first.
      for (const tool of Object.values(this.tools)) {
        if (tool == null) continue;
        if (tool.outputs == null && tool.error == null) {
          await tool.end(undefined, "Run not completed (conversation ended)");
        }
      }

      for (const subagent of Object.values(this.subagents)) {
        if (subagent == null) continue;
        if (subagent.end_time == null) {
          if (subagent.outputs == null && subagent.error == null) {
            await subagent.end(
              undefined,
              "Run not completed (conversation ended)",
            );
          } else {
            await subagent.end();
          }
        }
      }

      // First make sure all the runs are created
      await Promise.allSettled(this.postRunQueue);

      // Then patch the runs
      await Promise.allSettled(
        this.runTrees.map((runTree) => runTree.patchRun()),
      );
    } finally {
      this.dispose();
    }
  }
}

/**
 * Configuration options for wrapping Claude Agent SDK with LangSmith tracing.
 */
export type WrapClaudeAgentSDKConfig = Partial<
  Omit<
    RunTreeConfig,
    "inputs" | "outputs" | "run_type" | "child_runs" | "parent_run" | "error"
  >
>;
