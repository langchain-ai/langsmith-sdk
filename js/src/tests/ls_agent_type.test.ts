import { RunTree } from "../run_trees.js";
import {
  defaultLsAgentTypeMetadata,
  lsAgentTypeMetadata,
  resolveDefaultLsAgentType,
} from "../utils/ls_agent_type.js";

const fakeRunTree = () =>
  ({
    extra: { metadata: {} },
    createChild: () => undefined,
    postRun: () => undefined,
  }) as unknown as RunTree;

test("resolves root when no parent runtree", () => {
  expect(resolveDefaultLsAgentType(undefined)).toBe("root");
  expect(resolveDefaultLsAgentType(null)).toBe("root");
});

test("resolves undefined when nested under a runtree", () => {
  expect(resolveDefaultLsAgentType(fakeRunTree())).toBeUndefined();
});

test("resolves root for non-runtree values (e.g. ContextPlaceholder)", () => {
  expect(resolveDefaultLsAgentType({})).toBe("root");
  expect(resolveDefaultLsAgentType({ notARunTree: true })).toBe("root");
});

test("lsAgentTypeMetadata spreads tag when set", () => {
  expect(lsAgentTypeMetadata("root")).toEqual({ ls_agent_type: "root" });
  expect(lsAgentTypeMetadata("subagent")).toEqual({
    ls_agent_type: "subagent",
  });
});

test("lsAgentTypeMetadata skips key when undefined", () => {
  expect(lsAgentTypeMetadata(undefined)).toEqual({});
});

test("defaultLsAgentTypeMetadata stamps root when no parent and key absent", () => {
  expect(defaultLsAgentTypeMetadata({}, undefined)).toEqual({
    ls_agent_type: "root",
  });
});

test("defaultLsAgentTypeMetadata skips when nested and key absent", () => {
  expect(defaultLsAgentTypeMetadata({}, fakeRunTree())).toEqual({});
});

test("defaultLsAgentTypeMetadata preserves user-supplied value (returns empty delta)", () => {
  expect(
    defaultLsAgentTypeMetadata({ ls_agent_type: "middleware" }, undefined),
  ).toEqual({});
});

test("defaultLsAgentTypeMetadata preserves null opt-out (returns empty delta)", () => {
  expect(
    defaultLsAgentTypeMetadata({ ls_agent_type: null }, undefined),
  ).toEqual({});
});
