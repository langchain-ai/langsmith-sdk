import { openai } from "@ai-sdk/openai";
import { generateObject, generateText, streamObject, streamText } from "ai";
import { z } from "zod";
import { wrapAISDKModel } from "../wrappers/vercel.js";

test("AI SDK generateText", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { text } = await generateText({
    model: modelWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
  });
  console.log(text);
});

test("AI SDK generateObject", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { object } = await generateObject({
    model: modelWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
    schema: z.object({
      ingredients: z.array(z.string()),
    }),
  });
  console.log(object);
});

test("AI SDK streamText", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { textStream } = await streamText({
    model: modelWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
  });
  for await (const chunk of textStream) {
    console.log(chunk);
  }
});

test("AI SDK streamObject", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { partialObjectStream } = await streamObject({
    model: modelWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
    schema: z.object({
      ingredients: z.array(z.string()),
    }),
  });
  for await (const chunk of partialObjectStream) {
    console.log(chunk);
  }
});
