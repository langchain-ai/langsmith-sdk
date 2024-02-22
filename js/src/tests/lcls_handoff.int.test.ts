import { BaseMessage, HumanMessage } from "@langchain/core/messages";
import { RunnableConfig, RunnableLambda } from "@langchain/core/runnables";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { MessageGraph } from "@langchain/langgraph";
import { v4 as uuidv4 } from "uuid";
import { Client } from "../client.js";
import { Run } from "../schemas.js";
import { traceable } from "../traceable.js";
import { toArray, waitUntil } from "./utils.js";

test.concurrent(
  "Test handoff between run tree and LangChain code.",
  async () => {
    const projectName = `__test_handoff ${uuidv4()}`;

    // Define a new graph
    const workflow = new MessageGraph();

    const addValueTraceable = traceable(
      (msg: BaseMessage) => {
        return new HumanMessage({ content: msg.content + " world" });
      },
      {
        name: "add_negligible_value",
      }
    );

    const myFunc = async (messages: BaseMessage[], config?: RunnableConfig) => {
      const runnableConfig = config ?? { callbacks: [] };
      const newMsg = await addValueTraceable(
        runnableConfig,
        messages[0] as HumanMessage
      );
      return [newMsg];
    };

    // Define the two nodes we will cycle between
    workflow.addNode(
      "agent",
      new RunnableLambda({
        func: async () => new HumanMessage({ content: "Hello!" }),
      })
    );
    workflow.addNode("action", new RunnableLambda({ func: myFunc }));

    // Set the entrypoint as `agent`
    // This means that this node is the first one called
    workflow.setEntryPoint("agent");
    workflow.addEdge("agent", "action");
    workflow.setFinishPoint("action");
    const app = workflow.compile();
    const tracer = new LangChainTracer({ projectName });
    const client = new Client({
      callerOptions: { maxRetries: 3 },
      timeout_ms: 30_000,
    });
    try {
      const result = await app.invoke(
        [new HumanMessage({ content: "Hello!" })],
        {
          callbacks: [tracer],
        }
      );
      expect(result[result.length - 1].content).toEqual("Hello! world");

      // First wait until at least one trace is found in the project
      const getNestedFunction = (): Promise<Run[]> =>
        toArray(
          client.listRuns({
            projectName,
            filter: "eq(name, 'add_negligible_value')",
          })
        );
      await waitUntil(
        async () => {
          const traces = await getNestedFunction();
          return traces.length > 0;
        },
        120_000,
        10
      );

      const traces = await getNestedFunction();
      expect(traces.length).toEqual(1);
      const trace = traces[0];
      expect(trace.name).toEqual("add_negligible_value");
      expect(trace.parent_run_id).not.toBeNull();
    } catch (e) {
      console.error(e);
      throw e;
    } finally {
      await client.deleteProject({ projectName });
    }
  }
);
