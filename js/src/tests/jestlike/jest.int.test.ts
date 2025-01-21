import { test } from "@jest/globals";
import { OpenAIEmbeddings } from "@langchain/openai";

import * as ls from "../../jest/index.js";

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
