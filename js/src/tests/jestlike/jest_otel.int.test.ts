import * as ls from "../../jest/index.js";
import { initializeOTEL } from "../../experimental/otel/setup.js";
import { SimpleEvaluator } from "../../jest/index.js";
import { generateText, tool } from "ai";
import { traceable } from "../../traceable.js";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

initializeOTEL();

const myEvaluator: SimpleEvaluator = (params) => {
  const { referenceOutputs, outputs } = params;
  if (outputs.bar === referenceOutputs.bar) {
    return {
      key: "quality",
      score: 1,
    };
  } else if (outputs.bar === "goodval") {
    return {
      key: "quality",
      score: 0.5,
    };
  } else {
    return {
      key: "quality",
      score: 0,
    };
  }
};

// Must have LANGSMITH_OTEL_ENABLED=true in the actual env vars for this to pass
ls.describe.skip("js unit testing test demo with OTEL", () => {
  ls.test(
    "Should create an example with OTEL enabled",
    { inputs: { foo: "bar" }, referenceOutputs: { bar: "qux" } },
    async ({ inputs: _inputs }) => {
      ls.logFeedback({
        key: "readability",
        score: 0.9,
      });
      const wrappedText = traceable(
        async (content: string) => {
          const { text } = await generateText({
            model: openai("gpt-4.1-nano"),
            messages: [{ role: "user", content }],
            tools: {
              listOrders: tool({
                description: "list all orders",
                inputSchema: z.object({ userId: z.string() }),
                execute: async ({ userId }) => {
                  const getOrderNumber = traceable(
                    async () => {
                      return "1234";
                    },
                    { name: "getOrderNumber" }
                  );
                  const orderNumber = await getOrderNumber();
                  return `User ${userId} has the following orders: ${orderNumber}`;
                },
              }),
              viewTrackingInformation: tool({
                description: "view tracking information for a specific order",
                inputSchema: z.object({ orderId: z.string() }),
                execute: async ({ orderId }) =>
                  `Here is the tracking information for ${orderId}`,
              }),
            },
            experimental_telemetry: {
              isEnabled: true,
            },
          });

          return { text };
        },
        { name: "parentTraceable" }
      );
      await wrappedText("What are my orders");
      await ls
        .expect("foo")
        .evaluatedBy(myEvaluator)
        .not.toBeGreaterThanOrEqual(0.5);
      ls.logOutputs({
        otel: "is a thing that exists",
      });
    }
  );

  ls.test(
    "Should create a second example with OTEL enabled",
    { inputs: { foo: "bar2" }, referenceOutputs: { bar: "qux2" } },
    async ({ inputs: _inputs }) => {
      ls.logFeedback({
        key: "readability",
        score: 0.9,
      });
      ls.logFeedback({
        key: "quality",
        score: 0,
      });
      ls.logOutputs({
        otel: "is another thing that exists",
      });
    }
  );
});
