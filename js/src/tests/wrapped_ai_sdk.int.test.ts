import { anthropic } from "@ai-sdk/anthropic";
import { generateText, streamText } from "ai";
import { wrapAISDKModel } from "../wrappers/ai_sdk.js";

test.only("AI SDK", async () => {
  // const client = new Client({ autoBatchTracing: false });
  // const callSpy = jest
  //   // eslint-disable-next-line @typescript-eslint/no-explicit-any
  //   .spyOn((client as any).caller, "call")
  //   .mockResolvedValue({ ok: true, text: () => "" });
  const sdkWithTracing = wrapAISDKModel(
    anthropic("claude-3-haiku-20240307"),
    // { client }
  );
  // const wrappedStreamText = wrapSDK(streamText);
  const { textStream } = await streamText({
    model: sdkWithTracing,
    prompt: "Write a vegetarian lasagna recipe for 4 people.",
  });
  for await (const chunk of textStream) {
    console.log(chunk);
  }
  // const text = await generateText({
  //   model: sdkWithTracing,
  //   prompt: "Write a vegetarian lasagna recipe for 4 people.",
  // })
  // console.log(text);
});
