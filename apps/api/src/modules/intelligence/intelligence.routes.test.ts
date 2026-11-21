process.env.DB_URL = "postgres://fake:fake@localhost:5432/fake";

import { describe, it, expect, mock, beforeEach } from "bun:test";

// Hermetic mocks for auth, db, and project services
const authServicePath = import.meta.resolve("../auth/auth.service");
const dbPath = import.meta.resolve("../../db");
const projectsServicePath = import.meta.resolve("../projects/projects.service");

let mockDbRepos: Record<string, { id: string; projectId: string | null; userId: string; rootDirectory: string | null }> = {};
let mockUserProjects: Record<string, Set<string>> = {};

mock.module(authServicePath, () => ({
  verifySessionToken: async (token: string) => {
    if (token === "token-alice") return "user-alice";
    if (token === "token-bob") return "user-bob";
    return null;
  },
  getUserById: async (id: string) => {
    if (id === "user-alice") {
      return { id: "user-alice", email: "alice@gitami.dev", name: "Alice" };
    }
    if (id === "user-bob") {
      return { id: "user-bob", email: "bob@gitami.dev", name: "Bob" };
    }
    return null;
  },
}));

mock.module(dbPath, () => ({
  db: {
    select: () => ({
      from: () => ({
        where: (condition: any) => ({
          limit: () => {
            const requestedRepoName = condition?.queryChunks?.find(
              (c: any) =>
                c?.value &&
                typeof c?.value === "string" &&
                !Array.isArray(c?.value),
            )?.value;
            if (requestedRepoName && mockDbRepos[requestedRepoName]) {
              return Promise.resolve([mockDbRepos[requestedRepoName]]);
            }
            return Promise.resolve([]);
          },
        }),
      }),
    }),
  },
}));

mock.module(projectsServicePath, () => ({
  getProjectForUser: async (user: any, projectId: string) => {
    const userAllowed = mockUserProjects[user?.id];
    if (userAllowed && userAllowed.has(projectId)) {
      return {
        project: {
          id: projectId,
          name: `Project ${projectId}`,
          slug: `project-${projectId}`,
          organizationId: "org-alpha",
        },
        organization: {
          id: "org-alpha",
          name: "Alpha Organization",
        },
      };
    }
    return null;
  },
}));

// Dynamically import intelligenceRouter after registering mocks
const { default: intelligenceRouter, verifyAndEnrichTenancy } = await import("./intelligence.routes");

describe("Secure Intelligence Gateway Routes & Tenancy", () => {
  beforeEach(() => {
    mockDbRepos = {};
    mockUserProjects = {};
    globalThis.fetch = mock(() =>
      Promise.resolve(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    ) as any;
  });

  describe("Slice 1: Public Health Check", () => {
    it("allows GET /health without authentication token", async () => {
      globalThis.fetch = mock(() =>
        Promise.resolve(
          new Response(JSON.stringify({ status: "ok", service: "ai-service" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        )
      ) as any;

      const res = await intelligenceRouter.request("/health");
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.status).toBe("ok");
    });
  });

  describe("Slice 2: Unauthenticated Access Control Across All Functional Endpoints", () => {
    const unauthenticatedCases = [
      { method: "GET", path: "/repos" },
      { method: "GET", path: "/config" },
      { method: "GET", path: "/prompts" },
      { method: "GET", path: "/prompts/system" },
      { method: "PUT", path: "/prompts/system" },
      { method: "POST", path: "/prompts/system/reset" },
      { method: "GET", path: "/graph-report/facebook/react" },
      { method: "POST", path: "/chat", body: { message: "hi" } },
      { method: "POST", path: "/chat/stream", body: { message: "hi" } },
      { method: "POST", path: "/investigate", body: { message: "hi" } },
      { method: "POST", path: "/issue/analyze", body: { message: "hi" } },
      { method: "POST", path: "/doc/generate", body: { message: "hi" } },
      { method: "POST", path: "/code/plan", body: { message: "hi" } },
      { method: "POST", path: "/code/execute", body: { message: "hi" } },
    ];

    for (const testCase of unauthenticatedCases) {
      it(`rejects unauthenticated ${testCase.method} ${testCase.path} with 401`, async () => {
        const init: RequestInit = {
          method: testCase.method,
          headers: { "Content-Type": "application/json" },
        };
        if (testCase.body) {
          init.body = JSON.stringify(testCase.body);
        }
        const res = await intelligenceRouter.request(testCase.path, init);
        expect(res.status).toBe(401);
        const data = (await res.json()) as any;
        expect(data.error).toContain("Unauthorized");
      });
    }
  });

  describe("Slice 3: Tenancy Rejection for Unmapped or Missing Repositories", () => {
    it("rejects authenticated requests with unknown repo_id with 403 Forbidden", async () => {
      mockDbRepos = {};
      mockUserProjects["user-alice"] = new Set(["project-1"]);

      const res = await intelligenceRouter.request("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token-alice",
        },
        body: JSON.stringify({ message: "hello", repo_id: "unknown/repo" }),
      });

      expect(res.status).toBe(403);
      const data = (await res.json()) as any;
      expect(data.error).toContain("Forbidden");
    });

    it("fails closed with 403 when no repo_id or project_id is provided (no 'default' fallback)", async () => {
      mockUserProjects["user-alice"] = new Set(["project-1"]);

      const res = await intelligenceRouter.request("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token-alice",
        },
        body: JSON.stringify({ message: "hello without tenancy" }),
      });

      expect(res.status).toBe(403);
      const data = (await res.json()) as any;
      expect(data.error).toContain("Forbidden");
    });

    it("rejects repository unlinked to any project with 403 Forbidden", async () => {
      mockDbRepos["unlinked/repo"] = {
        id: "repo-orphan",
        projectId: null,
        userId: "user-alice",
        rootDirectory: null,
      };
      mockUserProjects["user-alice"] = new Set(["project-alpha"]);

      const res = await intelligenceRouter.request("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token-alice",
        },
        body: JSON.stringify({ message: "hello", repo_id: "unlinked/repo" }),
      });

      expect(res.status).toBe(403);
      const data = (await res.json()) as any;
      expect(data.error).toContain("not mapped to any project");
    });
  });

  describe("Slice 4: RBAC Rejection for Unauthorized Project Membership", () => {
    it("rejects authenticated user attempting to access a repository from an unauthorized project with 403", async () => {
      mockDbRepos["tenant-a/repo"] = {
        id: "repo-1",
        projectId: "project-alpha",
        userId: "user-alice",
        rootDirectory: "packages/core",
      };
      mockUserProjects["user-bob"] = new Set(["project-beta"]);

      const res = await intelligenceRouter.request("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token-bob",
        },
        body: JSON.stringify({ message: "read secret data", repo_id: "tenant-a/repo" }),
      });

      expect(res.status).toBe(403);
      const data = (await res.json()) as any;
      expect(data.error).toContain("Forbidden");
    });

    it("rejects GET /graph-report for unauthorized user with 403 Forbidden", async () => {
      mockDbRepos["tenant-a/repo"] = {
        id: "repo-1",
        projectId: "project-alpha",
        userId: "user-alice",
        rootDirectory: "packages/core",
      };
      mockUserProjects["user-bob"] = new Set(["project-beta"]);

      const res = await intelligenceRouter.request("/graph-report/tenant-a/repo", {
        method: "GET",
        headers: {
          Authorization: "Bearer token-bob",
        },
      });

      expect(res.status).toBe(403);
      const data = (await res.json()) as any;
      expect(data.error).toContain("Forbidden");
    });
  });

  describe("Slice 5: Tenancy Verification & Payload Attribute Injection", () => {
    it("injects validated project_id, team_id, user_id, and root_directory into forwarded payload for /chat", async () => {
      mockDbRepos["tenant-a/repo"] = {
        id: "repo-1",
        projectId: "project-alpha",
        userId: "user-alice",
        rootDirectory: "packages/core",
      };
      mockUserProjects["user-alice"] = new Set(["project-alpha"]);

      let forwardedPayload: any = null;
      globalThis.fetch = mock((url: string, init?: any) => {
        if (url.includes("/api/chat")) {
          forwardedPayload = JSON.parse(init.body);
          return Promise.resolve(
            new Response(JSON.stringify({ response: "AI chat answer" }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        return Promise.resolve(new Response("Not found", { status: 404 }));
      }) as any;

      const res = await intelligenceRouter.request("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token-alice",
        },
        body: JSON.stringify({
          message: "Explain architecture",
          repo_id: "tenant-a/repo",
          user_id: "malicious-user",
        }),
      });

      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.response).toBe("AI chat answer");

      expect(forwardedPayload).not.toBeNull();
      expect(forwardedPayload.project_id).toBe("project-alpha");
      expect(forwardedPayload.user_id).toBe("user-alice");
      expect(forwardedPayload.root_directory).toBe("packages/core");
      expect(forwardedPayload.team_id).toBe("org-alpha");
    });

    it("rejects request when supplied project_id mismatches repository project with 403", async () => {
      mockDbRepos["tenant-a/repo"] = {
        id: "repo-1",
        projectId: "project-alpha",
        userId: "user-alice",
        rootDirectory: "packages/core",
      };
      mockUserProjects["user-alice"] = new Set(["project-alpha"]);

      const res = await intelligenceRouter.request("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token-alice",
        },
        body: JSON.stringify({
          message: "Explain architecture",
          repo_id: "tenant-a/repo",
          project_id: "mismatched-project-id",
        }),
      });

      expect(res.status).toBe(403);
      const data = (await res.json()) as any;
      expect(data.error).toContain("does not match repository's assigned project");
    });

    it("verifies and forwards payloads across curated agent endpoints", async () => {
      mockDbRepos["tenant-a/repo"] = {
        id: "repo-1",
        projectId: "project-alpha",
        userId: "user-alice",
        rootDirectory: "src",
      };
      mockUserProjects["user-alice"] = new Set(["project-alpha"]);

      const curatedEndpoints = [
        "/investigate",
        "/issue/analyze",
        "/doc/generate",
        "/code/plan",
        "/code/execute",
      ];

      for (const endpoint of curatedEndpoints) {
        let forwardedPayload: any = null;
        globalThis.fetch = mock((url: string, init?: any) => {
          forwardedPayload = JSON.parse(init.body);
          return Promise.resolve(
            new Response(JSON.stringify({ success: true, endpoint }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }) as any;

        const res = await intelligenceRouter.request(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer token-alice",
          },
          body: JSON.stringify({ repo_id: "tenant-a/repo", prompt: "run task" }),
        });

        expect(res.status).toBe(200);
        expect(forwardedPayload.project_id).toBe("project-alpha");
        expect(forwardedPayload.user_id).toBe("user-alice");
      }
    });

    it("allows GET /graph-report for authorized user and queries AI service", async () => {
      mockDbRepos["tenant-a/repo"] = {
        id: "repo-1",
        projectId: "project-alpha",
        userId: "user-alice",
        rootDirectory: "packages/core",
      };
      mockUserProjects["user-alice"] = new Set(["project-alpha"]);

      let requestedUrl = "";
      globalThis.fetch = mock((url: string) => {
        requestedUrl = url;
        return Promise.resolve(
          new Response(JSON.stringify({ nodes: [], edges: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }) as any;

      const res = await intelligenceRouter.request("/graph-report/tenant-a/repo?branch=dev", {
        method: "GET",
        headers: {
          Authorization: "Bearer token-alice",
        },
      });

      expect(res.status).toBe(200);
      expect(requestedUrl).toContain("/api/graph-report/tenant-a%2Frepo?branch=dev");
    });
  });

  describe("Slice 6: Direct verifyAndEnrichTenancy Unit Seam", () => {
    it("throws 401 when user is missing or undefined", async () => {
      await expect(
        verifyAndEnrichTenancy({ repo_id: "any/repo" }, undefined)
      ).rejects.toThrow();
    });

    it("throws 403 when repository does not exist", async () => {
      mockDbRepos = {};
      const user = { id: "user-alice" };
      await expect(
        verifyAndEnrichTenancy({ repo_id: "missing/repo" }, user)
      ).rejects.toThrow();
    });

    it("throws 403 when user is not a member of project", async () => {
      mockDbRepos["repo/secret"] = {
        id: "repo-secret",
        projectId: "proj-secret",
        userId: "owner-bob",
        rootDirectory: null,
      };
      mockUserProjects["user-alice"] = new Set(["proj-public"]);
      const user = { id: "user-alice" };

      await expect(
        verifyAndEnrichTenancy({ repo_id: "repo/secret" }, user)
      ).rejects.toThrow();
    });

    it("successfully enriches tenancy when verified", async () => {
      mockDbRepos["repo/allowed"] = {
        id: "repo-allowed",
        projectId: "proj-allowed",
        userId: "owner-alice",
        rootDirectory: "subfolder",
      };
      mockUserProjects["user-alice"] = new Set(["proj-allowed"]);
      const user = { id: "user-alice" };

      const enriched = await verifyAndEnrichTenancy(
        { repo_id: "repo/allowed", message: "hi" },
        user
      );

      expect(enriched.project_id).toBe("proj-allowed");
      expect(enriched.user_id).toBe("user-alice");
      expect(enriched.root_directory).toBe("subfolder");
      expect(enriched.team_id).toBe("org-alpha");
      expect(enriched.message).toBe("hi");
    });
  });
});
