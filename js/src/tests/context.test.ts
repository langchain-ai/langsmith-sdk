/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { LangSmithConflictError } from "../utils/error.js";

function _mockClient() {
  const client = new Client({ apiKey: "test-api-key" });
  jest.spyOn(client as any, "_currentTenantIsOwner").mockResolvedValue(true);
  jest
    .spyOn(client as any, "_ownerConflictError")
    .mockImplementation(async () => new Error("owner mismatch"));
  return client;
}

function _response(body: unknown, status = 200): any {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
    headers: new Headers(),
  };
}

function _setFetchSequence(client: Client, responses: any[]): jest.Mock {
  const spy = jest.spyOn(client as any, "_fetch");
  for (const res of responses) {
    spy.mockResolvedValueOnce(res);
  }
  return spy as unknown as jest.Mock;
}

describe("Context (agent/skill) on Client", () => {
  describe("pullAgent", () => {
    it("hits the directories GET URL and merges owner/repo into response", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        _response({
          commit_id: "00000000-0000-0000-0000-000000000000",
          commit_hash: "abc12345",
          files: { "main.py": { type: "file", content: "print('hi')" } },
        }),
      ]);

      const agent = await client.pullAgent("owner/my-agent");

      const [url, init] = fetchSpy.mock.calls[0] as [string, any];
      expect(url).toContain(
        "/v1/platform/hub/repos/owner/my-agent/directories"
      );
      expect(init.method).toBe("GET");
      expect(agent.owner).toBe("owner");
      expect(agent.repo).toBe("my-agent");
      expect(agent.commit_hash).toBe("abc12345");
      expect(agent.files["main.py"]).toEqual({
        type: "file",
        content: "print('hi')",
      });
    });

    it("passes commit query param when version is supplied", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        _response({ commit_hash: "abc12345", files: {} }),
      ]);

      await client.pullAgent("owner/my-agent", { version: "abc12345" });

      const url = (fetchSpy.mock.calls[0] as [string, any])[0];
      expect(url).toContain("commit=abc12345");
    });
  });

  describe("pushAgent", () => {
    it("rejects more than 500 files", async () => {
      const client = _mockClient();
      const tooMany: Record<string, any> = {};
      for (let i = 0; i < 501; i++) {
        tooMany[`p_${i}.py`] = { type: "file", content: "x" };
      }
      await expect(
        client.pushAgent("-/repo", { files: tooMany })
      ).rejects.toThrow(/Too many files/);
    });

    it("rejects short parentCommit", async () => {
      const client = _mockClient();
      await expect(
        client.pushAgent("-/repo", { files: {}, parentCommit: "abc" })
      ).rejects.toThrow(/8-64/);
    });

    it("rejects invalid repo_handle when creating", async () => {
      const client = _mockClient();
      _setFetchSequence(client, [
        // GET /repos/-/BadName → 404 (doesn't exist)
        _response({ detail: "Not Found" }, 404),
      ]);
      await expect(
        client.pushAgent("-/BadName", {
          files: { "main.py": { type: "file", content: "x" } },
        })
      ).rejects.toThrow(/Invalid repo_handle/);
    });

    it("creates new repo then commits files when repo does not exist", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        // _repoExists GET → 404
        _response({ detail: "Not Found" }, 404),
        // _createRepo POST → ok
        _response({ repo: { id: "r1" } }),
        // commit POST → ok
        _response({
          commit: {
            id: "00000000-0000-0000-0000-000000000000",
            commit_hash: "abc12345",
          },
        }),
      ]);

      const url = await client.pushAgent("-/my-agent", {
        files: { "main.py": { type: "file", content: "x" } },
      });
      expect(url).toContain("/hub/-/my-agent:abc12345");

      const calls = fetchSpy.mock.calls as [string, any][];
      expect(calls).toHaveLength(3);
      // 1. exists check
      expect(calls[0][0]).toContain("/repos/-/my-agent");
      expect(calls[0][1].method).toBe("GET");
      // 2. create repo
      expect(calls[1][0]).toContain("/repos/");
      expect(calls[1][1].method).toBe("POST");
      const createBody = JSON.parse(calls[1][1].body);
      expect(createBody.repo_handle).toBe("my-agent");
      expect(createBody.repo_type).toBe("agent");
      // 3. commit
      expect(calls[2][0]).toContain(
        "/v1/platform/hub/repos/-/my-agent/directories/commits"
      );
      expect(calls[2][1].method).toBe("POST");
      const commitBody = JSON.parse(calls[2][1].body);
      expect(commitBody.files).toEqual({
        "main.py": { type: "file", content: "x" },
      });
    });

    it("patches metadata when repo exists and metadata fields are provided", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        // _repoExists → 200 (exists)
        _response({ repo: { repo_handle: "my-agent" } }),
        // _updateRepoMetadata PATCH
        _response({}),
        // commit
        _response({
          commit: {
            id: "00000000-0000-0000-0000-000000000000",
            commit_hash: "abc12345",
          },
        }),
      ]);

      await client.pushAgent("-/my-agent", {
        files: { "main.py": { type: "file", content: "x" } },
        description: "new desc",
      });

      const calls = fetchSpy.mock.calls as [string, any][];
      expect(calls).toHaveLength(3);
      expect(calls[1][0]).toContain("/repos/-/my-agent");
      expect(calls[1][1].method).toBe("PATCH");
      const patchBody = JSON.parse(calls[1][1].body);
      expect(patchBody).toEqual({ description: "new desc" });
    });

    it("skips metadata patch when repo exists and no metadata fields given", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        _response({ repo: { repo_handle: "my-agent" } }),
        _response({
          commit: {
            id: "00000000-0000-0000-0000-000000000000",
            commit_hash: "abc12345",
          },
        }),
      ]);

      await client.pushAgent("-/my-agent", {
        files: { "main.py": { type: "file", content: "x" } },
      });

      const calls = fetchSpy.mock.calls as [string, any][];
      expect(calls).toHaveLength(2);
      expect(calls[1][1].method).toBe("POST");
    });

    it("swallows 409 from _createRepo (repo already exists)", async () => {
      const client = _mockClient();
      _setFetchSequence(client, [
        _response({ detail: "Not Found" }, 404),
        // _createRepo POST → 409
        _response({ detail: "already exists" }, 409),
        // commit
        _response({
          commit: {
            id: "00000000-0000-0000-0000-000000000000",
            commit_hash: "abc12345",
          },
        }),
      ]);

      await expect(
        client.pushAgent("-/my-agent", {
          files: { "main.py": { type: "file", content: "x" } },
        })
      ).resolves.toContain("/hub/-/my-agent:abc12345");
    });

    it("serializes null entry for deletion", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        _response({ repo: { repo_handle: "my-agent" } }),
        _response({
          commit: {
            id: "00000000-0000-0000-0000-000000000000",
            commit_hash: "abc12345",
          },
        }),
      ]);

      await client.pushAgent("-/my-agent", {
        files: { "gone.md": null },
      });

      const commitCall = (fetchSpy.mock.calls as [string, any][])[1];
      const body = JSON.parse(commitCall[1].body);
      expect(body.files).toEqual({ "gone.md": null });
    });
  });

  describe("deleteAgent", () => {
    it("hits DELETE on the directories URL", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [_response({}, 204)]);
      await client.deleteAgent("-/old-agent");
      const [url, init] = fetchSpy.mock.calls[0] as [string, any];
      expect(url).toContain("/v1/platform/hub/repos/-/old-agent/directories");
      expect(init.method).toBe("DELETE");
    });
  });

  describe("agentExists / skillExists", () => {
    it("returns true on 200", async () => {
      const client = _mockClient();
      _setFetchSequence(client, [_response({ repo: { id: "r1" } })]);
      expect(await client.agentExists("-/my-agent")).toBe(true);
    });

    it("returns false on 404", async () => {
      const client = _mockClient();
      _setFetchSequence(client, [_response({ detail: "Not Found" }, 404)]);
      expect(await client.agentExists("-/nope")).toBe(false);
    });
  });

  describe("listAgents", () => {
    it("sends repo_type=agent and paginates", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        _response({
          repos: [{ repo_handle: "a1" }, { repo_handle: "a2" }],
          total: 2,
        }),
      ]);

      const items: any[] = [];
      for await (const item of client.listAgents()) {
        items.push(item);
      }

      expect(items).toHaveLength(2);
      const url = (fetchSpy.mock.calls[0] as [string, any])[0];
      expect(url).toContain("/repos");
      expect(url).toContain("repo_type=agent");
    });

    it("forwards isPublic and query params", async () => {
      const client = _mockClient();
      const fetchSpy = _setFetchSequence(client, [
        _response({ repos: [], total: 0 }),
      ]);

      for await (const _ of client.listSkills({
        isPublic: true,
        query: "foo",
      })) {
        /* noop */
      }

      const url = (fetchSpy.mock.calls[0] as [string, any])[0];
      expect(url).toContain("repo_type=skill");
      expect(url).toContain("is_public=true");
      expect(url).toContain("query=foo");
    });
  });

  describe("LangSmithConflictError import", () => {
    it("is an Error subclass", () => {
      const e = new LangSmithConflictError("test");
      expect(e).toBeInstanceOf(Error);
      expect(e.name).toBe("LangSmithConflictError");
    });
  });
});
