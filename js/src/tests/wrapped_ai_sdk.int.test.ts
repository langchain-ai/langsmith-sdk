import { openai } from "@ai-sdk/openai";
import {
  generateObject,
  generateText,
  streamObject,
  streamText,
  tool,
} from "ai";
import { z } from "zod";
import { wrapAISDKModel } from "../wrappers/vercel.js";

const DEBUG = false;
test("AI SDK generateText", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { text } = await generateText({
    model: modelWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
  });
  DEBUG && console.log(text);
});

test("AI SDK generateText with a tool", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { text } = await generateText({
    model: modelWithTracing,
    prompt:
      "Write a vegetarian lasagna recipe for 4 people. Get ingredients first.",
    tools: {
      getIngredients: tool({
        description: "get a list of ingredients",
        parameters: z.object({
          ingredients: z.array(z.string()),
        }),
        execute: async () =>
          JSON.stringify(["pasta", "tomato", "cheese", "onions"]),
      }),
    },
    maxSteps: 2,
  });
  DEBUG && console.log(text);
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
  DEBUG && console.log(object);
});

test("AI SDK streamText", async () => {
  const modelWithTracing = wrapAISDKModel(openai("gpt-4o-mini"));
  const { textStream } = await streamText({
    model: modelWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
  });
  for await (const chunk of textStream) {
    DEBUG && console.log(chunk);
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
    DEBUG && console.log(chunk);
  }
});
