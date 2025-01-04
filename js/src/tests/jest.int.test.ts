import { test } from "@jest/globals";
import { OpenAIEmbeddings } from "@langchain/openai";

import * as ls from "../jest/index.js";

const myEvaluator: ls.SimpleEvaluator = ({ expected, actual }) => {
  if (actual.bar === expected.bar) {
    return {
      key: "quality",
      score: 1,
    };
  } else if (actual.bar === "goodval") {
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

const embeddings = new OpenAIEmbeddings({
  model: "text-embedding-3-small",
});

test("Should test relative closeness custom matcher", async () => {
  await ls.expect("carrot").toBeSemanticCloseTo("carrot cake", {
    threshold: 0.5,
    embeddings,
  });
  await ls.expect("carrot").not.toBeSemanticCloseTo("airplane", {
    threshold: 0.5,
    embeddings,
  });
  await ls.expect("carrot").not.toBeSemanticCloseTo("airplane", {
    threshold: 0,
    embeddings,
  });
  await ls.expect("carrot").toBeSemanticCloseTo("airplane", {
    threshold: 1,
    embeddings,
  });
});

ls.describe("js unit testing test demo", () => {
  ls.test.each("*", { n: 3, metadata: { source: "langsmith" } })(
    "Pulls from current dataset in LangSmith",
    async ({ inputs: _inputs, outputs: _outputs }) => {
      const myApp = () => {
        return { bar: "goodval" };
      };
      const res = myApp();
      await ls.expect(res).evaluatedBy(myEvaluator).toBeGreaterThanOrEqual(0.5);
      return res;
    }
  );
});
