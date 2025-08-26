import type { OpenAI } from "openai";
import type { APIPromise } from "openai";
import type { RunTreeConfig } from "../index.js";
import {
  isTraceableFunction,
  traceable,
  TraceableConfig,
} from "../traceable.js";
import { KVMap } from "../schemas.js";

// Extra leniency around types in case multiple OpenAI SDK versions get installed
type OpenAIType = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  beta?: any;
  chat: {
    completions: {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      create: (...args: any[]) => any;
      parse: (...args: any[]) => any;
    };
  };
  completions: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    create: (...args: any[]) => any;
  };
  responses?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    create: (...args: any[]) => any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    retrieve: (...args: any[]) => any;
  };
};

type ExtraRunTreeConfig = Pick<
  Partial<RunTreeConfig>,
  "name" | "metadata" | "tags"
>;

type PatchedOpenAIClient<T extends OpenAIType> = T & {
  chat: T["chat"] & {
    completions: T["chat"]["completions"] & {
      create: {
        (
          arg: OpenAI.ChatCompletionCreateParamsStreaming,
          arg2?: OpenAI.RequestOptions & { langsmithExtra?: ExtraRunTreeConfig }
        ): APIPromise<AsyncGenerator<OpenAI.ChatCompletionChunk>>;
      } & {
        (
          arg: OpenAI.ChatCompletionCreateParamsNonStreaming,
          arg2?: OpenAI.RequestOptions & { langsmithExtra?: ExtraRunTreeConfig }
        ): APIPromise<OpenAI.ChatCompletion>;
      };
    };
  };
  completions: T["completions"] & {
    create: {
      (
        arg: OpenAI.CompletionCreateParamsStreaming,
        arg2?: OpenAI.RequestOptions & { langsmithExtra?: ExtraRunTreeConfig }
      ): APIPromise<AsyncGenerator<OpenAI.Completion>>;
    } & {
      (
        arg: OpenAI.CompletionCreateParamsNonStreaming,
        arg2?: OpenAI.RequestOptions & { langsmithExtra?: ExtraRunTreeConfig }
      ): APIPromise<OpenAI.Completion>;
    };
  };
};

function _combineChatCompletionChoices(
  choices: OpenAI.ChatCompletionChunk.Choice[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): any {
  const reversedChoices = choices.slice().reverse();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const message: { [key: string]: any } = {
    role: "assistant",
    content: "",
  };
  for (const c of reversedChoices) {
    if (c.delta.role) {
      message["role"] = c.delta.role;
      break;
    }
  }
  const toolCalls: {
    [
      key: number
    ]: Partial<OpenAI.Chat.Completions.ChatCompletionChunk.Choice.Delta.ToolCall>[];
  } = {};
  for (const c of choices) {
    if (c.delta.content) {
      message.content = message.content.concat(c.delta.content);
    }
    if (c.delta.function_call) {
      if (!message.function_call) {
        message.function_call = { name: "", arguments: "" };
      }
      if (c.delta.function_call.name) {
        message.function_call.name += c.delta.function_call.name;
      }
      if (c.delta.function_call.arguments) {
        message.function_call.arguments += c.delta.function_call.arguments;
      }
    }
    if (c.delta.tool_calls) {
      for (const tool_call of c.delta.tool_calls) {
        if (!toolCalls[c.index]) {
          toolCalls[c.index] = [];
        }
        toolCalls[c.index].push(tool_call);
      }
    }
  }
  if (Object.keys(toolCalls).length > 0) {
    message.tool_calls = [...Array(Object.keys(toolCalls).length)];
    for (const [index, toolCallChunks] of Object.entries(toolCalls)) {
      const idx = parseInt(index);
      message.tool_calls[idx] = {
        index: idx,
        id: toolCallChunks.find((c) => c.id)?.id || null,
        type: toolCallChunks.find((c) => c.type)?.type || null,
      };
      for (const chunk of toolCallChunks) {
        if (chunk.function) {
          if (!message.tool_calls[idx].function) {
            message.tool_calls[idx].function = {
              name: "",
              arguments: "",
            };
          }
          if (chunk.function.name) {
            message.tool_calls[idx].function.name += chunk.function.name;
          }
          if (chunk.function.arguments) {
            message.tool_calls[idx].function.arguments +=
              chunk.function.arguments;
          }
        }
      }
    }
  }
  return {
    index: choices[0].index,
    finish_reason: reversedChoices.find((c) => c.finish_reason) || null,
    message: message,
  };
}

const chatAggregator = (chunks: OpenAI.ChatCompletionChunk[]) => {
  if (!chunks || chunks.length === 0) {
    return { choices: [{ message: { role: "assistant", content: "" } }] };
  }
  const choicesByIndex: {
    [index: number]: OpenAI.ChatCompletionChunk.Choice[];
  } = {};
  for (const chunk of chunks) {
    for (const choice of chunk.choices) {
      if (choicesByIndex[choice.index] === undefined) {
        choicesByIndex[choice.index] = [];
      }
      choicesByIndex[choice.index].push(choice);
    }
  }

  const aggregatedOutput = chunks[chunks.length - 1];
  aggregatedOutput.choices = Object.values(choicesByIndex).map((choices) =>
    _combineChatCompletionChoices(choices)
  );

  return aggregatedOutput;
};

const responsesAggregator = (events: any[]) => {
  if (!events || events.length === 0) {
    return {};
  }

  // Find the response.completed event which contains the final response
  for (const event of events) {
    if (event.type === "response.completed" && event.response) {
      return event.response;
    }
  }

  // If no completed event found, return the last event
  return events[events.length - 1] || {};
};

const textAggregator = (
  allChunks: OpenAI.Completions.Completion[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Record<string, any> => {
  if (allChunks.length === 0) {
    return { choices: [{ text: "" }] };
  }
  const allContent: string[] = [];
  for (const chunk of allChunks) {
    const content = chunk.choices[0].text;
    if (content != null) {
      allContent.push(content);
    }
  }
  const content = allContent.join("");
  const aggregatedOutput = allChunks[allChunks.length - 1];
  aggregatedOutput.choices = [
    { ...aggregatedOutput.choices[0], text: content },
  ];
  return aggregatedOutput;
};

function processChatCompletion(outputs: Readonly<KVMap>): KVMap {
  const chatCompletion = outputs as OpenAI.ChatCompletion;
  // copy the original object, minus usage
  const result = { ...chatCompletion } as KVMap;
  const usage = chatCompletion.usage;
  if (usage) {
    const inputTokenDetails = {
      ...(usage.prompt_tokens_details?.audio_tokens !== null && {
        audio: usage.prompt_tokens_details?.audio_tokens,
      }),
      ...(usage.prompt_tokens_details?.cached_tokens !== null && {
        cache_read: usage.prompt_tokens_details?.cached_tokens,
      }),
    };
    const outputTokenDetails = {
      ...(usage.completion_tokens_details?.audio_tokens !== null && {
        audio: usage.completion_tokens_details?.audio_tokens,
      }),
      ...(usage.completion_tokens_details?.reasoning_tokens !== null && {
        reasoning: usage.completion_tokens_details?.reasoning_tokens,
      }),
    };
    result.usage_metadata = {
      input_tokens: usage.prompt_tokens ?? 0,
      output_tokens: usage.completion_tokens ?? 0,
      total_tokens: usage.total_tokens ?? 0,
      ...(Object.keys(inputTokenDetails).length > 0 && {
        input_token_details: inputTokenDetails,
      }),
      ...(Object.keys(outputTokenDetails).length > 0 && {
        output_token_details: outputTokenDetails,
      }),
    };
  }
  delete result.usage;
  return result;
}

/**
 * Wraps an OpenAI client's completion methods, enabling automatic LangSmith
 * tracing. Method signatures are unchanged, with the exception that you can pass
 * an additional and optional "langsmithExtra" field within the second parameter.
 * @param openai An OpenAI client instance.
 * @param options LangSmith options.
 * @example
 * ```ts
 * import { OpenAI } from "openai";
 * import { wrapOpenAI } from "langsmith/wrappers/openai";
 *
 * const patchedClient = wrapOpenAI(new OpenAI());
 *
 * const patchedStream = await patchedClient.chat.completions.create(
 *   {
 *     messages: [{ role: "user", content: `Say 'foo'` }],
 *     model: "gpt-4.1-mini",
 *     stream: true,
 *   },
 *   {
 *     langsmithExtra: {
 *       metadata: {
 *         additional_data: "bar",
 *       },
 *     },
 *   },
 * );
 * ```
 */
export const wrapOpenAI = <T extends OpenAIType>(
  openai: T,
  options?: Partial<RunTreeConfig>
): PatchedOpenAIClient<T> => {
  if (
    isTraceableFunction(openai.chat.completions.create) ||
    isTraceableFunction(openai.completions.create)
  ) {
    throw new Error(
      "This instance of OpenAI client has been already wrapped once."
    );
  }

  // Attempt to determine if this is an Azure OpenAI client
  const isAzureOpenAI = openai.constructor?.name === "AzureOpenAI";

  const provider = isAzureOpenAI ? "azure" : "openai";
  const chatName = isAzureOpenAI ? "AzureChatOpenAI" : "ChatOpenAI";
  const completionsName = isAzureOpenAI ? "AzureOpenAI" : "OpenAI";

  // Some internal OpenAI methods call each other, so we need to preserve original
  // OpenAI methods.
  const tracedOpenAIClient = { ...openai };

  const chatCompletionParseMetadata: TraceableConfig<
    typeof openai.chat.completions.create
  > = {
    name: chatName,
    run_type: "llm",
    aggregator: chatAggregator,
    argsConfigPath: [1, "langsmithExtra"],
    getInvocationParams: (payload: unknown) => {
      if (typeof payload !== "object" || payload == null) return undefined;
      // we can safely do so, as the types are not exported in TSC
      const params = payload as OpenAI.ChatCompletionCreateParams;

      const ls_stop =
        (typeof params.stop === "string" ? [params.stop] : params.stop) ??
        undefined;

      return {
        ls_provider: provider,
        ls_model_type: "chat",
        ls_model_name: params.model,
        ls_max_tokens:
          params.max_completion_tokens ?? params.max_tokens ?? undefined,
        ls_temperature: params.temperature ?? undefined,
        ls_stop,
      };
    },
    processOutputs: processChatCompletion,
    ...options,
  };

  if (openai.beta) {
    tracedOpenAIClient.beta = openai.beta;

    if (
      openai.beta.chat &&
      openai.beta.chat.completions &&
      typeof openai.beta.chat.completions.parse === "function"
    ) {
      tracedOpenAIClient.beta.chat.completions.parse = traceable(
        openai.beta.chat.completions.parse.bind(openai.beta.chat.completions),
        chatCompletionParseMetadata
      );
    }
  }

  tracedOpenAIClient.chat = {
    ...openai.chat,
    completions: Object.create(Object.getPrototypeOf(openai.chat.completions)),
  };

  // Copy all own properties and then wrap specific methods
  Object.assign(tracedOpenAIClient.chat.completions, openai.chat.completions);

  // Wrap chat.completions.create
  tracedOpenAIClient.chat.completions.create = traceable(
    openai.chat.completions.create.bind(openai.chat.completions),
    chatCompletionParseMetadata
  );

  // Wrap chat.completions.parse if it exists
  if (typeof openai.chat.completions.parse === "function") {
    tracedOpenAIClient.chat.completions.parse = traceable(
      openai.chat.completions.parse.bind(openai.chat.completions),
      chatCompletionParseMetadata
    );
  }

  tracedOpenAIClient.completions = {
    ...openai.completions,
    create: traceable(openai.completions.create.bind(openai.completions), {
      name: completionsName,
      run_type: "llm",
      aggregator: textAggregator,
      argsConfigPath: [1, "langsmithExtra"],
      getInvocationParams: (payload: unknown) => {
        if (typeof payload !== "object" || payload == null) return undefined;
        // we can safely do so, as the types are not exported in TSC
        const params = payload as OpenAI.CompletionCreateParams;

        const ls_stop =
          (typeof params.stop === "string" ? [params.stop] : params.stop) ??
          undefined;

        return {
          ls_provider: provider,
          ls_model_type: "llm",
          ls_model_name: params.model,
          ls_max_tokens: params.max_tokens ?? undefined,
          ls_temperature: params.temperature ?? undefined,
          ls_stop,
        };
      },
      ...options,
    }),
  };

  // Add responses API support if it exists
  if (openai.responses) {
    // Create a new object with the same prototype to preserve all methods
    tracedOpenAIClient.responses = Object.create(
      Object.getPrototypeOf(openai.responses)
    );

    // Copy all own properties
    if (tracedOpenAIClient.responses) {
      Object.assign(tracedOpenAIClient.responses, openai.responses);
    }

    // Wrap responses.create method
    if (
      tracedOpenAIClient.responses &&
      typeof tracedOpenAIClient.responses.create === "function"
    ) {
      tracedOpenAIClient.responses.create = traceable(
        openai.responses.create.bind(openai.responses),
        {
          name: chatName,
          run_type: "llm",
          aggregator: responsesAggregator,
          argsConfigPath: [1, "langsmithExtra"],
          getInvocationParams: (payload: unknown) => {
            if (typeof payload !== "object" || payload == null)
              return undefined;
            // Handle responses API parameters
            const params = payload as any;
            return {
              ls_provider: provider,
              ls_model_type: "llm",
              ls_model_name: params.model || "unknown",
            };
          },
          processOutputs: processChatCompletion,
          ...options,
        }
      );
    }
  }

  return tracedOpenAIClient as PatchedOpenAIClient<T>;
};
