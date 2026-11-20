process.env.DB_URL = "postgres://fake:fake@localhost:5432/fake";

import { describe, it, expect, mock, beforeEach } from "bun:test";
import { triggerTrackedIncrementalReindex } from "./webhook.service";
import { db } from "../../db";

describe("Webhook Incremental Ingestion & Task Persistence", () => {
  beforeEach(() => {
    mock.restore();
  });

  it("consumes NDJSON stream and transitions task record to COMPLETED", async () => {
    const updateCalls: any[] = [];
    mock.module("../../db", () => ({
      db: {
        update: () => ({
          set: (vals: any) => ({
            where: () => {
              updateCalls.push(vals);
              return Promise.resolve();
            },
          }),
        }),
      },
    }));

    // Mock global fetch to return an NDJSON stream
    const ndjsonChunks = [
      JSON.stringify({ stage: "DIFF", status: "RUNNING", stats: { files_discovered: 2 } }) + "\n",
      JSON.stringify({ stage: "AST_ANALYSIS", status: "RUNNING", stats: { files_parsed: 2 } }) + "\n",
      JSON.stringify({ stage: "GRAPH_SYNC", status: "RUNNING", stats: { entities_created: 4 } }) + "\n",
      JSON.stringify({ stage: "COMPLETED", status: "COMPLETED", stats: { entities_created: 4 } }) + "\n",
    ];

    const stream = new ReadableStream({
      start(controller) {
        for (const chunk of ndjsonChunks) {
          controller.enqueue(new TextEncoder().encode(chunk));
        }
        controller.close();
      },
    });

    globalThis.fetch = mock(() =>
      Promise.resolve(
        new Response(stream, {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        })
      )
    ) as any;

    await triggerTrackedIncrementalReindex({
      jobId: "job-123",
      repoId: "owner/repo",
      baseSha: "sha1",
      headSha: "sha2",
      branch: "main",
      projectId: "proj-1",
      accessToken: "token-abc",
    });

    expect(updateCalls.length).toBeGreaterThanOrEqual(4);
    const lastUpdate = updateCalls[updateCalls.length - 1];
    expect(lastUpdate.stage).toBe("COMPLETED");
    expect(lastUpdate.status).toBe("COMPLETED");
    expect(lastUpdate.stats.entities_created).toBe(4);
  });

  it("handles unexpected stream disconnection and marks task as FAILED", async () => {
    const updateCalls: any[] = [];
    mock.module("../../db", () => ({
      db: {
        update: () => ({
          set: (vals: any) => ({
            where: () => {
              updateCalls.push(vals);
              return Promise.resolve();
            },
          }),
        }),
      },
    }));

    // Stream closes abruptly without terminal COMPLETED/FAILED
    const ndjsonChunks = [
      JSON.stringify({ stage: "DIFF", status: "RUNNING" }) + "\n",
    ];

    const stream = new ReadableStream({
      start(controller) {
        for (const chunk of ndjsonChunks) {
          controller.enqueue(new TextEncoder().encode(chunk));
        }
        controller.close();
      },
    });

    globalThis.fetch = mock(() =>
      Promise.resolve(
        new Response(stream, {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        })
      )
    ) as any;

    await triggerTrackedIncrementalReindex({
      jobId: "job-456",
      repoId: "owner/repo",
      baseSha: "sha1",
      headSha: "sha2",
      branch: "main",
      projectId: "proj-1",
    });

    const lastUpdate = updateCalls[updateCalls.length - 1];
    expect(lastUpdate.status).toBe("FAILED");
    expect(lastUpdate.error).toContain("disconnected unexpectedly");
  });

  it("handles pull_request.closed merged webhook by creating QUEUED incremental job", async () => {
    const { handleEvent } = await import("./webhook.service");

    const insertedJobs: any[] = [];
    mock.module("../../db", () => ({
      db: {
        update: () => ({
          set: () => ({
            where: () => Promise.resolve(),
          }),
        }),
        select: () => ({
          from: () => ({
            where: () => ({
              limit: () => Promise.resolve([{ projectId: "proj-999" }]),
            }),
          }),
        }),
        insert: () => ({
          values: (vals: any) => {
            insertedJobs.push(vals);
            return {
              returning: () => Promise.resolve([{ id: "job-created-1", ...vals }]),
            };
          },
        }),
      },
    }));

    // Mock github app helpers
    mock.module("./github-app.service", () => ({
      getIngestedRepoNames: () => Promise.resolve(["owner/repo"]),
      isRepoIngested: () => true,
      getInstallationTokenForRepo: () => Promise.resolve("mock-token"),
    }));

    globalThis.fetch = mock(() =>
      Promise.resolve(
        new Response("", {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson" },
        })
      )
    ) as any;

    const result = await handleEvent("pull_request", {
      action: "closed",
      pull_request: {
        number: 42,
        title: "Feature PR",
        merged: true,
        head: { sha: "headSha123" },
        base: { sha: "baseSha123", ref: "main" },
      },
      repository: {
        full_name: "owner/repo",
      },
    });

    expect(result.handled).toBe(true);
    expect(result.action).toBe("pr_closed_merged");
    expect(insertedJobs.length).toBe(1);
    expect(insertedJobs[0].type).toBe("INCREMENTAL");
    expect(insertedJobs[0].status).toBe("QUEUED");
    expect(insertedJobs[0].baseCommitSha).toBe("baseSha123");
    expect(insertedJobs[0].targetCommitSha).toBe("headSha123");
  });
});
