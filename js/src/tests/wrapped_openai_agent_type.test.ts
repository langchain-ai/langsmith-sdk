import { RunTree } from "../run_trees.js";
import { withRunTree } from "../singletons/traceable.js";
import { _resolveLsAgentType } from "../wrappers/openai.js";

const buildParent = (metadata: Record<string, unknown> | undefined) =>
  ({
    extra: metadata !== undefined ? { metadata } : {},
  }) as unknown as RunTree;

test("defaults to root when no parent runtree is present", () => {
  expect(_resolveLsAgentType({})).toBe("root");
});

test.each(["middleware", "subagent", "compaction"] as const)(
  "inherits narrowing parent tag '%s'",
  async (parentTag) => {
    const parent = buildParent({ ls_agent_type: parentTag });
    const resolved = await withRunTree(parent, () =>
      Promise.resolve(_resolveLsAgentType({})),
    );
    expect(resolved).toBe(parentTag);
  },
);

test("defaults to root when parent has no ls_agent_type", async () => {
  const parent = buildParent({});
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(_resolveLsAgentType({})),
  );
  expect(resolved).toBe("root");
});

test("defaults to root when parent's ls_agent_type is 'root'", async () => {
  const parent = buildParent({ ls_agent_type: "root" });
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(_resolveLsAgentType({})),
  );
  expect(resolved).toBe("root");
});

test.each(["root", "subagent", "middleware", "compaction"] as const)(
  "respects user-supplied per-call tag '%s' over parent inheritance",
  async (userTag) => {
    const parent = buildParent({ ls_agent_type: "middleware" });
    const resolved = await withRunTree(parent, () =>
      Promise.resolve(_resolveLsAgentType({ ls_agent_type: userTag })),
    );
    expect(resolved).toBe(userTag);
  },
);

test("ignores invalid user-supplied tag and falls through to inheritance", async () => {
  const parent = buildParent({ ls_agent_type: "middleware" });
  const resolved = await withRunTree(parent, () =>
    Promise.resolve(_resolveLsAgentType({ ls_agent_type: "bogus" })),
  );
  expect(resolved).toBe("middleware");
});
