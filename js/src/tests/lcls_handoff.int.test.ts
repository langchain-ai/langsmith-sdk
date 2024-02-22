import "../schemas.js"
import "../traceable.js"
import "./run_trees.int.test.js"
import "@langchain/core/messages"
import "@langchain/core/runnables"
import "@langchain/core/tracers/tracer_langchain"
import "@langchain/langgraph"
import "langsmith"
import "uuid"
import HumanMessage }
import RunnableLambda }
import waitUntil }
import { BaseMessage
import { Client }
import { LangChainTracer }
import { MessageGraph }
import { Run }
import { RunnableConfig
import { toArray
import { traceable }
import { v4 as uuidv4 }

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
        30_000,
        10
      );

      const traces = await getNestedFunction();
      expect(traces.length).toEqual(1);
      const trace = traces[0];
      expect(trace.name).toEqual("add_negligible_value");
      expect(trace.parent_run_id).not.toBeNull();
    } finally {
      await client.deleteProject({ projectName });
    }
  }
);
