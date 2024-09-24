import OpenAI from "openai";
import { pull } from "langchain/hub";

import { convertPromptToOpenAI } from "../openai.js";

test("basic traceable implementation", async () => {
  const prompt = await pull("jacob/joke-generator");
  const formattedPrompt = await prompt.invoke({
    topic: "cats",
  });

  const { messages } = convertPromptToOpenAI(formattedPrompt);

  const openAIClient = new OpenAI();

  const openAIResponse = await openAIClient.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
  });

  expect(openAIResponse.choices.length).toBeGreaterThan(0);
});
