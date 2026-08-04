import { RunTree } from "../run_trees.js";
import { withRunTree } from "../traceable.js";
import {
  vercelLsAgentTypeMetadata,
  resolveVercelLsAgentType,
} from "../experimental/vercel/_agent_type.js";

// createChild/postRun stubs let the mock parent pass isRunTree.
const buildParent = (
  metadata: Record<string, unknown> | undefined,
  runType?: string,
) =>
  ({
    run_type: runType,
    extra: metadata !== undefined ? { metadata } : {},
    createChild: () => undefined,
    postRun: () => Promise.resolve(),
  }) as unknown as RunTree;

test("returns root when no parent runtree (top-level Vercel call)", () => {
  expect(resolveVercelLsAgentType()).toBe("root");
});

test("returns undefined when nested with untagged parent and not tool", async () => {
  const parent = buildParent({}, "chain");
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(resolveVercelLsAgentType()),
  );
  expect(resolved).toBeUndefined();
});

test.each(["root", "middleware", "subagent", "compaction"] as const)(
  "inherits user-supplied parent tag '%s' from ambient runtree",
  async (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    const resolved = await withRunTree(parent, () =>
      Promise.resolve(resolveVercelLsAgentType()),
    );
    expect(resolved).toBe(parentTag);
  },
);

test.each(["root", "middleware", "subagent", "compaction"] as const)(
  "inherits user-supplied parent tag '%s' from explicitly-passed runtree",
  (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    expect(resolveVercelLsAgentType(parent)).toBe(parentTag);
  },
);

test("returns subagent when parent.run_type='tool' (Vercel convention)", () => {
  const parent = buildParent({}, "tool");
  expect(resolveVercelLsAgentType(parent)).toBe("subagent");
});

test.each(["middleware", "subagent", "compaction"] as const)(
  "user narrowing tag '%s' beats parent.run_type='tool'",
  (narrowingTag) => {
    const parent = buildParent({ ls_agent_type: narrowingTag }, "tool");
    expect(resolveVercelLsAgentType(parent)).toBe(narrowingTag);
  },
);

test("parent.run_type='tool' overrides inherited root (structural detection)", () => {
  const parent = buildParent({ ls_agent_type: "root" }, "tool");
  expect(resolveVercelLsAgentType(parent)).toBe("subagent");
});

test("invalid parent tag falls through to run_type/undefined", () => {
  const nonTool = buildParent({ ls_agent_type: "bogus" }, "chain");
  expect(resolveVercelLsAgentType(nonTool)).toBeUndefined();

  const tool = buildParent({ ls_agent_type: "bogus" }, "tool");
  expect(resolveVercelLsAgentType(tool)).toBe("subagent");
});

test("null on parent's ls_agent_type falls through to undefined", () => {
  const parent = buildParent({ ls_agent_type: null }, "chain");
  expect(resolveVercelLsAgentType(parent)).toBeUndefined();
});

test("non-RunTree parent returns root (safety default)", () => {
  expect(resolveVercelLsAgentType(null)).toBe("root");
  expect(resolveVercelLsAgentType("not-a-runtree")).toBe("root");
  expect(resolveVercelLsAgentType(42)).toBe("root");
  // ContextPlaceholder (tracingEnabled=false) — treated as no parent.
  expect(resolveVercelLsAgentType({ tracingEnabled: false })).toBe("root");
});

test("spread helper yields { ls_agent_type } when a tag resolves", () => {
  expect(vercelLsAgentTypeMetadata()).toEqual({ ls_agent_type: "root" });
});

test("spread helper yields {} when resolver returns undefined", async () => {
  const parent = buildParent({}, "chain");
  const spread = await withRunTree(parent, () =>
    Promise.resolve(vercelLsAgentTypeMetadata()),
  );
  expect(spread).toEqual({});
});
