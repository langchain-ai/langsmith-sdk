import { RunTree } from "../run_trees.js";
// Import withRunTree from the top-level traceable module — its module-load side
// effect installs the real AsyncLocalStorage instance the helper reads from.
import { withRunTree } from "../traceable.js";
import { _resolveLsAgentType } from "../wrappers/openai.js";

const buildParent = (metadata: Record<string, unknown> | undefined) =>
  ({
    extra: metadata !== undefined ? { metadata } : {},
  }) as unknown as RunTree;

test("stamps root at trace root (no parent runtree)", () => {
  expect(_resolveLsAgentType({})).toBe("root");
});

test("returns undefined when nested and no per-call user tag", async () => {
  const parent = buildParent({});
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(_resolveLsAgentType({})),
  );
  expect(resolved).toBeUndefined();
});

test.each(["root", "middleware", "subagent", "compaction"] as const)(
  "returns undefined when nested under parent tagged '%s' (propagation carries it)",
  async (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    const resolved = await withRunTree(parent, () =>
      Promise.resolve(_resolveLsAgentType({})),
    );
    expect(resolved).toBeUndefined();
  },
);

test.each(["root", "subagent", "middleware", "compaction"] as const)(
  "respects user-supplied per-call tag '%s'",
  (userTag) => {
    expect(_resolveLsAgentType({ ls_agent_type: userTag })).toBe(userTag);
  },
);

test("null per-call opts out (returns undefined)", () => {
  expect(_resolveLsAgentType({ ls_agent_type: null })).toBeUndefined();
});

test("invalid per-call tag falls through at top level to root default", () => {
  expect(_resolveLsAgentType({ ls_agent_type: "bogus" })).toBe("root");
});

test("invalid per-call tag falls through when nested to undefined", async () => {
  const parent = buildParent({ ls_agent_type: "middleware" });
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(_resolveLsAgentType({ ls_agent_type: "bogus" })),
  );
  expect(resolved).toBeUndefined();
});
