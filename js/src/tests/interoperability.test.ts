import { Runnable, RunnableLambda } from "@langchain/core/runnables";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { traceable } from "../traceable.js";
import { mockClient } from "./utils/mock_client.js";
import type { Client } from "../index.js";

function getPermutations<T>(array: T[]): T[][] {
  const results: T[][] = [];

  function permute(arr: T[], m: T[] = []) {
    if (arr.length === 0) {
      results.push(m);
    } else {
      for (let i = 0; i < arr.length; i++) {
        const curr = arr.slice();
        const next = curr.splice(i, 1);
        permute(curr.slice(), m.concat(next));
      }
    }
  }

  permute(array);
  return results;
}

const createRunnableLambdaWithWrappedCall = (
  fn: (input: string[]) => Promise<string[]>
) => {
  return RunnableLambda.from(async (input: string[]) => {
    const res = await fn(input);
    return res.concat(["RunnableLambda"]);
  });
};

// Need to pass mocked client all the way down
const createTraceableWithWrappedCall = (
  fn: (input: string[]) => Promise<string[]>,
  client: Client
) => {
  return traceable(
    async (input: string[]) => {
      const res = await fn(input);
      return res.concat(["traceable"]);
    },
    {
      client,
      tracingEnabled: true,
    }
  );
};

const entries = [
  {
    name: "RunnableLambda",
    base: () =>
      RunnableLambda.from(async (input: string[]) => {
        return input.concat(["RunnableLambda"]);
      }),
    wrap: createRunnableLambdaWithWrappedCall,
  },
  {
    name: "traceable",
    base: (client: Client) =>
      traceable(
        async (input: string[]) => {
          return input.concat(["traceable"]);
        },
        { client, tracingEnabled: true }
      ),
    wrap: createTraceableWithWrappedCall,
  },
];

const normalizeFn = (input: Runnable | ((...args: any[]) => Promise<any>)) => {
  if (typeof input === "function") {
    return input;
  }
  return input.invoke.bind(input);
};

// Wrap due to funny Jest .each signature
const permutations = getPermutations(entries).map((permutation) => ({
  permutation,
}));

test.each(permutations)(
  "Test traceable permutation: %s",
  async ({ permutation }) => {
    const { client, callSpy } = mockClient();
    let currentFn = permutation[0].base(client);
    for (const entry of permutation.slice(1)) {
      currentFn = entry.wrap(normalizeFn(currentFn), client);
    }
    let res;
    if (typeof currentFn === "function") {
      res = await currentFn([]);
    } else {
      const tracer = new LangChainTracer({
        // Needed since we end up with a wrapped "langsmith"
        // package because "langchain" itself depends on "langsmith"
        // and resolutions can't figure it out
        client: client as any,
      });
      res = await currentFn.invoke([], {
        callbacks: [tracer],
      });
    }
    const finalCall = callSpy.mock.calls[callSpy.mock.calls.length - 1];
    const finalCallArgs = finalCall[2] as any;
    expect(finalCallArgs).toBeDefined();
    const finalCallOutputs = JSON.parse(finalCallArgs.body).outputs;
    const finalCallOutput = finalCallOutputs[Object.keys(finalCallOutputs)[0]];
    console.log(finalCallOutput, permutation.map((p) => p.name));
    expect(finalCallOutput).toEqual(permutation.map((p) => p.name));
  }
);
