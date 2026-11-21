import { describe, it, expect, mock } from "bun:test";
import { createHmac } from "node:crypto";
import {
  signInternalServiceToken,
  verifyInternalServiceToken,
  getInternalAuthHeaders,
  fetchWithInternalAuth,
  INTERNAL_AUTH_HEADER,
} from "./internal-auth";
import { env } from "../configs/env";

describe("Internal Service Authentication & HMAC Signing", () => {
  const testSecret = "test-secret-key-12345";
  const testTimestamp = 1700000000000;

  it("exports the canonical internal auth header name", () => {
    expect(INTERNAL_AUTH_HEADER).toBe("X-Gitami-Internal-Auth");
  });

  describe("signInternalServiceToken()", () => {
    it("generates a token formatted as <timestamp>.<signature>", async () => {
      const token = await signInternalServiceToken({ secret: testSecret });
      expect(typeof token).toBe("string");
      const parts = token.split(".");
      expect(parts.length).toBe(2);

      const [timestampStr, signature] = parts;
      expect(timestampStr).toBeDefined();
      expect(signature).toBeDefined();

      const timestampNum = parseInt(timestampStr!, 10);
      expect(Number.isFinite(timestampNum)).toBe(true);
      expect(Math.abs(Date.now() - timestampNum)).toBeLessThan(5000);

      // Signature should be 64-character hex string (SHA256 = 32 bytes = 64 hex chars)
      expect(signature).toMatch(/^[a-f0-9]{64}$/);
    });

    it("matches expected HMAC-SHA256 digest against independent Node crypto reference", async () => {
      // Independent source of truth calculation
      const expectedDigest = createHmac("sha256", testSecret)
        .update(testTimestamp.toString())
        .digest("hex");

      const token = await signInternalServiceToken({
        secret: testSecret,
        timestamp: testTimestamp,
      });

      expect(token).toBe(`${testTimestamp}.${expectedDigest}`);
    });

    it("uses env.INTERNAL_API_SECRET by default when no secret override is passed", async () => {
      const now = Date.now();
      const expectedDigest = createHmac("sha256", env.INTERNAL_API_SECRET)
        .update(now.toString())
        .digest("hex");

      const token = await signInternalServiceToken({ timestamp: now });
      expect(token).toBe(`${now}.${expectedDigest}`);
    });
  });

  describe("verifyInternalServiceToken()", () => {
    it("validates a freshly signed token successfully", async () => {
      const now = Date.now();
      const token = await signInternalServiceToken({
        secret: testSecret,
        timestamp: now,
      });

      const result = await verifyInternalServiceToken(token, {
        secret: testSecret,
        currentTime: now + 500,
      });

      expect(result.valid).toBe(true);
      expect(result.reason).toBeUndefined();
    });

    it("rejects token with invalid/tampered signature", async () => {
      const now = Date.now();
      const tamperedToken = `${now}.0000000000000000000000000000000000000000000000000000000000000000`;

      const result = await verifyInternalServiceToken(tamperedToken, {
        secret: testSecret,
        currentTime: now,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toContain("signature");
    });

    it("rejects token when secret does not match", async () => {
      const now = Date.now();
      const token = await signInternalServiceToken({
        secret: "secret-a",
        timestamp: now,
      });

      const result = await verifyInternalServiceToken(token, {
        secret: "secret-b",
        currentTime: now,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toContain("signature");
    });

    it("rejects expired token when clock drift exceeds 60,000ms (replay protection)", async () => {
      const pastTime = Date.now() - 65000;
      const expiredToken = await signInternalServiceToken({
        secret: testSecret,
        timestamp: pastTime,
      });

      const result = await verifyInternalServiceToken(expiredToken, {
        secret: testSecret,
        currentTime: Date.now(),
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toContain("expired");
    });

    it("rejects future token when clock drift exceeds 60,000ms", async () => {
      const futureTime = Date.now() + 65000;
      const futureToken = await signInternalServiceToken({
        secret: testSecret,
        timestamp: futureTime,
      });

      const result = await verifyInternalServiceToken(futureToken, {
        secret: testSecret,
        currentTime: Date.now(),
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toContain("expired");
    });

    it("rejects malformed tokens lacking proper separator or non-numeric timestamp", async () => {
      const invalidTokens = [
        "not-a-token",
        "12345",
        "abc.def",
        "123.456.789",
        "",
      ];

      for (const invalid of invalidTokens) {
        const result = await verifyInternalServiceToken(invalid, {
          secret: testSecret,
        });
        expect(result.valid).toBe(false);
        expect(result.reason).toBeDefined();
      }
    });
  });

  describe("getInternalAuthHeaders()", () => {
    it("returns an object containing the X-Gitami-Internal-Auth header with valid token", async () => {
      const headers = await getInternalAuthHeaders({ secret: testSecret });
      expect(headers[INTERNAL_AUTH_HEADER]).toBeDefined();

      const token = headers[INTERNAL_AUTH_HEADER];
      const verification = await verifyInternalServiceToken(token, {
        secret: testSecret,
      });
      expect(verification.valid).toBe(true);
    });
  });

  describe("fetchWithInternalAuth()", () => {
    it("attaches X-Gitami-Internal-Auth header to outgoing fetch requests", async () => {
      let interceptedHeaders: Headers | null = null;
      const originalFetch = globalThis.fetch;
      globalThis.fetch = mock((_url: any, init?: any) => {
        interceptedHeaders = new Headers(init?.headers);
        return Promise.resolve(new Response(JSON.stringify({ ok: true })));
      }) as any;

      try {
        const response = await fetchWithInternalAuth("http://localhost:8000/api/repos", {
          headers: { "Content-Type": "application/json" },
        }, { secret: testSecret });

        expect(response.status).toBe(200);
        expect(interceptedHeaders).not.toBeNull();
        const token = interceptedHeaders!.get(INTERNAL_AUTH_HEADER);
        expect(token).not.toBeNull();

        const verification = await verifyInternalServiceToken(token!, { secret: testSecret });
        expect(verification.valid).toBe(true);
      } finally {
        globalThis.fetch = originalFetch;
      }
    });
  });
});
