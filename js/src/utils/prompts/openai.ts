/* eslint-disable import/no-extraneous-dependencies */
import type { BasePromptValue } from "@langchain/core/prompt_values";
import * as langChainOpenAIImports from "@langchain/openai";
import type { OpenAI } from "openai";

/**
 * Convert a formatted LangChain prompt (e.g. pulled from the hub) into
 * a format expected by OpenAI's JS SDK.
 *
 * Requires the "@langchain/openai" package to be installed in addition
 * to the OpenAI SDK.
 *
 * @example
 * ```ts
 * import { convertPromptToOpenAI } from "langsmith/utils/hub/openai";
 * import { pull } from "langchain/hub";
 *
 * import OpenAI from 'openai';
 *
 * const prompt = await pull("jacob/joke-generator");
 * const formattedPrompt = await prompt.invoke({
 *   topic: "cats",
 * });
 *
 * const { messages } = convertPromptToOpenAI(formattedPrompt);
 *
 * const openAIClient = new OpenAI();
 *
 * const openaiResponse = await openAIClient.chat.completions.create({
 *   model: "gpt-4o",
 *   messages,
 * });
 * ```
 * @param formattedPrompt
 * @returns A partial OpenAI payload.
 */
export function convertPromptToOpenAI(formattedPrompt: BasePromptValue): {
  messages: OpenAI.Chat.ChatCompletionMessageParam[];
} {
  const messages = formattedPrompt.toChatMessages();
  const { _convertMessagesToOpenAIParams } = langChainOpenAIImports;
  if (typeof _convertMessagesToOpenAIParams !== "function") {
    throw new Error(
      `Please update your version of "@langchain/openai" to 0.3.1 or higher.`
    );
  }
  return {
    messages: _convertMessagesToOpenAIParams(
      messages
    ) as OpenAI.Chat.ChatCompletionMessageParam[],
  };
}
