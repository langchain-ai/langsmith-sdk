import { RunTree } from "../run_trees.js";
// Import `withRunTree` from the top-level traceable module; its module-load
// side effect installs the real Node AsyncLocalStorage, which the shared
// `_agent_type.ts` helper depends on. Importing directly from
// `singletons/traceable.js` leaves the mock ALS in place and `getStore`
// never returns the parent — exactly the behavior real users see when
// `traceable` is on the app's import graph, which is the case in practice.
import { withRunTree } from "../traceable.js";
import { resolveLsAgentType } from "../experimental/vercel/_agent_type.js";

const buildParent = (
  metadata: Record<string, unknown> | undefined,
  runType?: string,
) =>
  ({
    run_type: runType,
    extra: metadata !== undefined ? { metadata } : {},
  }) as unknown as RunTree;

test("defaults to root when no parent runtree is present", () => {
  expect(resolveLsAgentType()).toBe("root");
});

test("explicit undefined parent → root", () => {
  expect(resolveLsAgentType(undefined)).toBe("root");
});

test.each(["middleware", "subagent", "compaction"] as const)(
  "inherits narrowing parent tag '%s' from ambient runtree",
  async (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    const resolved = await withRunTree(parent, () =>
      Promise.resolve(resolveLsAgentType()),
    );
    expect(resolved).toBe(parentTag);
  },
);

test.each(["middleware", "subagent", "compaction"] as const)(
  "inherits narrowing parent tag '%s' from explicitly-passed runtree",
  (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    expect(resolveLsAgentType(parent)).toBe(parentTag);
  },
);

test("parent.run_type='tool' → subagent (Vercel convention preserved)", () => {
  const parent = buildParent({}, "tool");
  expect(resolveLsAgentType(parent)).toBe("subagent");
});

test("parent narrowing tag beats parent.run_type='tool'", () => {
  const parent = buildParent({ ls_agent_type: "middleware" }, "tool");
  expect(resolveLsAgentType(parent)).toBe("middleware");
});

test("parent tagged 'root' falls through to run_type check", () => {
  const withTool = buildParent({ ls_agent_type: "root" }, "tool");
  expect(resolveLsAgentType(withTool)).toBe("subagent");

  const withoutTool = buildParent({ ls_agent_type: "root" }, "chain");
  expect(resolveLsAgentType(withoutTool)).toBe("root");
});

test("parent without ls_agent_type falls through to run_type/default", () => {
  const nonTool = buildParent({}, "chain");
  expect(resolveLsAgentType(nonTool)).toBe("root");

  const tool = buildParent({}, "tool");
  expect(resolveLsAgentType(tool)).toBe("subagent");
});

test("invalid parent tag falls through", () => {
  const parent = buildParent({ ls_agent_type: "bogus" }, "chain");
  expect(resolveLsAgentType(parent)).toBe("root");
});

test("explicit non-object parent → root", () => {
  expect(resolveLsAgentType(null)).toBe("root");
  expect(resolveLsAgentType("not-a-runtree")).toBe("root");
  expect(resolveLsAgentType(42)).toBe("root");
});
