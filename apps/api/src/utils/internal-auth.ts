import { env } from "../configs/env";

export const INTERNAL_AUTH_HEADER = "X-Gitami-Internal-Auth";
export const DEFAULT_MAX_DRIFT_MS = 60000;

export interface InternalAuthOptions {
  secret?: string;
  timestamp?: number | string;
}

export interface VerifyInternalAuthOptions {
  secret?: string;
  maxDriftMs?: number;
  currentTime?: number;
}

export interface VerificationResult {
  valid: boolean;
  reason?: string;
}

/**
 * Resolves the internal API secret key from options or environment configuration.
 */
function resolveSecret(customSecret?: string): string {
  return (
    customSecret ||
    process.env.INTERNAL_API_SECRET ||
    env.INTERNAL_API_SECRET ||
    "gitami_dev_internal_api_secret_default_32bytes"
  );
}

/**
 * Signs an internal service-to-service authentication token using HMAC-SHA256
 * via Web Crypto API. Produces a token formatted as `<timestamp>.<signature>`.
 */
export async function signInternalServiceToken(
  options: InternalAuthOptions = {},
): Promise<string> {
  const secret = resolveSecret(options.secret);
  const timestamp = (options.timestamp !== undefined ? options.timestamp : Date.now()).toString();

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const signatureBuffer = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(timestamp),
  );

  const signatureHex = Array.from(new Uint8Array(signatureBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return `${timestamp}.${signatureHex}`;
}

/**
 * Verifies an internal service token against the shared secret and checks for
 * timestamp drift (replay protection).
 */
export async function verifyInternalServiceToken(
  token: string,
  options: VerifyInternalAuthOptions = {},
): Promise<VerificationResult> {
  if (!token || typeof token !== "string") {
    return { valid: false, reason: "Missing or invalid token string" };
  }

  const parts = token.split(".");
  if (parts.length !== 2) {
    return { valid: false, reason: "Malformed token format: expected <timestamp>.<signature>" };
  }

  const [timestampStr, providedSignature] = parts;
  if (!timestampStr || !providedSignature) {
    return { valid: false, reason: "Malformed token format: expected <timestamp>.<signature>" };
  }

  const timestampNum = parseInt(timestampStr, 10);
  if (isNaN(timestampNum) || !Number.isFinite(timestampNum) || timestampStr.trim() !== timestampNum.toString()) {
    return { valid: false, reason: "Invalid timestamp in token" };
  }

  const currentTime = options.currentTime ?? Date.now();
  const maxDriftMs = options.maxDriftMs ?? DEFAULT_MAX_DRIFT_MS;

  if (Math.abs(currentTime - timestampNum) > maxDriftMs) {
    return { valid: false, reason: `Token expired: drift exceeds ${maxDriftMs}ms (replay protection)` };
  }

  if (!/^[a-f0-9]{64}$/i.test(providedSignature)) {
    return { valid: false, reason: "Invalid signature format: expected 64-char hex string" };
  }

  const effectiveSecret = resolveSecret(options.secret);
  const encoder = new TextEncoder();

  const sigBytes = new Uint8Array(
    (providedSignature.match(/.{1,2}/g) || []).map((byte) => parseInt(byte, 16)),
  );

  try {
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(effectiveSecret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"],
    );

    const isValid = await crypto.subtle.verify(
      "HMAC",
      key,
      sigBytes,
      encoder.encode(timestampStr),
    );

    if (!isValid) {
      return { valid: false, reason: "Invalid internal service signature" };
    }

    return { valid: true };
  } catch (err: any) {
    return { valid: false, reason: `Verification error: ${err?.message || "Unknown error"}` };
  }
}

/**
 * Returns HTTP headers containing the generated X-Gitami-Internal-Auth token.
 */
export async function getInternalAuthHeaders(
  options?: InternalAuthOptions,
): Promise<{ [INTERNAL_AUTH_HEADER]: string }> {
  const token = await signInternalServiceToken(options);
  return {
    [INTERNAL_AUTH_HEADER]: token,
  };
}

/**
 * Reusable HTTP client wrapper that injects X-Gitami-Internal-Auth header into outbound requests.
 */
export async function fetchWithInternalAuth(
  input: string | URL | Request,
  init: RequestInit = {},
  options?: InternalAuthOptions,
): Promise<Response> {
  const authHeaders = await getInternalAuthHeaders(options);
  const headers = new Headers(init.headers);
  headers.set(INTERNAL_AUTH_HEADER, authHeaders[INTERNAL_AUTH_HEADER]);

  return fetch(input, {
    ...init,
    headers,
  });
}
