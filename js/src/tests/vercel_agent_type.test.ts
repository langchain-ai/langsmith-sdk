import { RunTree } from "../run_trees.js";
import { withRunTree } from "../traceable.js";
import {
  lsAgentTypeMetadata,
  resolveLsAgentType,
} from "../experimental/vercel/_agent_type.js";

const buildParent = (
  metadata: Record<string, unknown> | undefined,
  runType?: string,
) =>
  ({
    run_type: runType,
    extra: metadata !== undefined ? { metadata } : {},
  }) as unknown as RunTree;

test("returns root when no parent runtree (top-level Vercel call)", () => {
  expect(resolveLsAgentType()).toBe("root");
});

test("returns undefined when nested with untagged parent and not tool", async () => {
  const parent = buildParent({}, "chain");
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(resolveLsAgentType()),
  );
  expect(resolved).toBeUndefined();
});

test.each(["root", "middleware", "subagent", "compaction"] as const)(
  "inherits user-supplied parent tag '%s' from ambient runtree",
  async (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    const resolved = await withRunTree(parent, () =>
      Promise.resolve(resolveLsAgentType()),
    );
    expect(resolved).toBe(parentTag);
  },
);

test.each(["root", "middleware", "subagent", "compaction"] as const)(
  "inherits user-supplied parent tag '%s' from explicitly-passed runtree",
  (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    expect(resolveLsAgentType(parent)).toBe(parentTag);
  },
);

test("returns subagent when parent.run_type='tool' (Vercel convention)", () => {
  const parent = buildParent({}, "tool");
  expect(resolveLsAgentType(parent)).toBe("subagent");
});

test.each(["middleware", "subagent", "compaction"] as const)(
  "user narrowing tag '%s' beats parent.run_type='tool'",
  (narrowingTag) => {
    const parent = buildParent({ ls_agent_type: narrowingTag }, "tool");
    expect(resolveLsAgentType(parent)).toBe(narrowingTag);
  },
);

test("parent.run_type='tool' overrides inherited root (structural detection)", () => {
  const parent = buildParent({ ls_agent_type: "root" }, "tool");
  expect(resolveLsAgentType(parent)).toBe("subagent");
});

test("invalid parent tag falls through to run_type/undefined", () => {
  const nonTool = buildParent({ ls_agent_type: "bogus" }, "chain");
  expect(resolveLsAgentType(nonTool)).toBeUndefined();

  const tool = buildParent({ ls_agent_type: "bogus" }, "tool");
  expect(resolveLsAgentType(tool)).toBe("subagent");
});

test("non-object parent returns root (safety default)", () => {
  expect(resolveLsAgentType(null)).toBe("root");
  expect(resolveLsAgentType("not-a-runtree")).toBe("root");
  expect(resolveLsAgentType(42)).toBe("root");
});

test("spread helper yields { ls_agent_type } when a tag resolves", () => {
  expect(lsAgentTypeMetadata()).toEqual({ ls_agent_type: "root" });
});

test("spread helper yields {} when resolver returns undefined", async () => {
  const parent = buildParent({}, "chain");
  const spread = await withRunTree(parent, () =>
    Promise.resolve(lsAgentTypeMetadata()),
  );
  expect(spread).toEqual({});
});
