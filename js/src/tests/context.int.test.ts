import { v4 as uuidv4 } from "uuid";
import { Client } from "../client.js";
import { AgentContext, FileEntry, SkillContext } from "../schemas.js";

function agentIdentifier(): string {
  return `-/ctx-test-js-agent-${uuidv4().slice(0, 8)}`;
}

function skillIdentifier(): string {
  return `-/ctx-test-js-skill-${uuidv4().slice(0, 8)}`;
}

describe("Context integration (agent/skill)", () => {
  const client = new Client();

  async function cleanupAgent(identifier: string) {
    try {
      await client.deleteAgent(identifier);
    } catch (_) {
      /* best effort */
    }
  }

  async function cleanupSkill(identifier: string) {
    try {
      await client.deleteSkill(identifier);
    } catch (_) {
      /* best effort */
    }
  }

  test("pushAgent + pullAgent roundtrip", async () => {
    const identifier = agentIdentifier();
    try {
      const url = await client.pushAgent(identifier, {
        files: {
          "AGENTS.md": { type: "file", content: "# Test Agent\n" },
        },
        description: "integration test agent (js)",
      });
      expect(url).toContain("/hub/");

      const agent: AgentContext = await client.pullAgent(identifier);
      expect(agent.files["AGENTS.md"]).toBeDefined();
      const entry = agent.files["AGENTS.md"] as FileEntry;
      expect(entry.type).toBe("file");
      expect(entry.content).toBe("# Test Agent\n");
    } finally {
      await cleanupAgent(identifier);
    }
  });

  test("pushSkill + pullSkill roundtrip", async () => {
    const identifier = skillIdentifier();
    try {
      const url = await client.pushSkill(identifier, {
        files: {
          "SKILL.md": { type: "file", content: "# Test Skill\n" },
        },
        description: "integration test skill (js)",
      });
      expect(url).toContain("/hub/");

      const skill: SkillContext = await client.pullSkill(identifier);
      expect(skill.files["SKILL.md"]).toBeDefined();
      const entry = skill.files["SKILL.md"] as FileEntry;
      expect(entry.content).toBe("# Test Skill\n");
    } finally {
      await cleanupSkill(identifier);
    }
  });

  test("pushAgent with null entry deletes that file", async () => {
    const identifier = agentIdentifier();
    try {
      await client.pushAgent(identifier, {
        files: {
          "keep.md": { type: "file", content: "keep" },
          "remove.md": { type: "file", content: "remove" },
        },
      });
      let agent = await client.pullAgent(identifier);
      expect(agent.files["keep.md"]).toBeDefined();
      expect(agent.files["remove.md"]).toBeDefined();

      await client.pushAgent(identifier, {
        files: { "remove.md": null },
      });
      agent = await client.pullAgent(identifier);
      expect(agent.files["keep.md"]).toBeDefined();
      expect(agent.files["remove.md"]).toBeUndefined();
    } finally {
      await cleanupAgent(identifier);
    }
  });

  test("pushAgent second commit updates file content", async () => {
    const identifier = agentIdentifier();
    try {
      await client.pushAgent(identifier, {
        files: { "AGENTS.md": { type: "file", content: "v1" } },
      });
      await client.pushAgent(identifier, {
        files: { "AGENTS.md": { type: "file", content: "v2" } },
      });

      const agent = await client.pullAgent(identifier);
      const entry = agent.files["AGENTS.md"] as FileEntry;
      expect(entry.content).toBe("v2");
    } finally {
      await cleanupAgent(identifier);
    }
  });

  test("deleteAgent removes the repo", async () => {
    const identifier = agentIdentifier();
    await client.pushAgent(identifier, {
      files: { "AGENTS.md": { type: "file", content: "x" } },
    });
    await client.pullAgent(identifier);

    await client.deleteAgent(identifier);

    await expect(client.pullAgent(identifier)).rejects.toThrow();
  });

  test("listAgents returns pushed agent", async () => {
    const identifier = agentIdentifier();
    const handle = identifier.split("/")[1];
    try {
      await client.pushAgent(identifier, {
        files: { "AGENTS.md": { type: "file", content: "x" } },
      });
      let found = false;
      for await (const repo of client.listAgents({ query: handle })) {
        if (repo.repo_handle === handle) {
          found = true;
          break;
        }
      }
      expect(found).toBe(true);
    } finally {
      await cleanupAgent(identifier);
    }
  });

  test("deleteSkill removes the repo", async () => {
    const identifier = skillIdentifier();
    await client.pushSkill(identifier, {
      files: { "SKILL.md": { type: "file", content: "x" } },
    });
    await client.pullSkill(identifier);

    await client.deleteSkill(identifier);

    await expect(client.pullSkill(identifier)).rejects.toThrow();
  });

  test("listSkills returns pushed skill", async () => {
    const identifier = skillIdentifier();
    const handle = identifier.split("/")[1];
    try {
      await client.pushSkill(identifier, {
        files: { "SKILL.md": { type: "file", content: "x" } },
      });
      let found = false;
      for await (const repo of client.listSkills({ query: handle })) {
        if (repo.repo_handle === handle) {
          found = true;
          break;
        }
      }
      expect(found).toBe(true);
    } finally {
      await cleanupSkill(identifier);
    }
  });
});
