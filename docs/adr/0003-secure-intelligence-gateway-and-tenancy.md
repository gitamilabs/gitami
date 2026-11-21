# ADR 0003: Secure Intelligence Gateway & Multi-Tenant Control Seam

> **Status:** Accepted  
> **Date:** November 2026  
> **Deciders:** Aryan Racha, System Architect  
> **Consulted:** GLOSSARY.md, ADR 0001, ADR 0002  

---

## Context & Problem Statement

Gitami operates on a strict two-tier architecture: the Bun control plane (`apps/api`) serves client web traffic and manages authentication/RBAC, while the Python Intelligence Service (`apps/ai`) hosts the Neo4j Knowledge Graph, ChromaDB Vector Store, and Curated Agents.

A security and tenancy audit revealed four critical vulnerabilities along this seam:
1. **Unmounted Gateway Authentication:** In [`apps/api/src/modules/intelligence/intelligence.routes.ts`](file:///home/aryanracha/Coding/projects/gitami/apps/api/src/modules/intelligence/intelligence.routes.ts), `authMiddleware` was imported but never mounted via `intelligenceRouter.use("*", authMiddleware)`. Consequently, all intelligence endpoints (`/chat`, `/chat/stream`, `/investigate`, `/issue/analyze`, `/doc/generate`, `/code/plan`, `/code/execute`, `/repos`, `/graph-report/*`, `/prompts/*`) were exposed completely unauthenticated.
2. **Cross-Tenant Isolation Collapse:** The helper `enrichPayloadWithTenancy` performed an unauthenticated database lookup on `connectedRepositories.fullName`. If unauthenticated or if the repository record was missing, it defaulted `project_id` to `"default"`. Crucially, it never validated that the requesting user belonged to the organization or project owning the repository. Any caller could query or manipulate knowledge bases of other tenants.
3. **Missing Service-to-Service Trust Boundary:** The Python Intelligence Service on port 8000 lacked authentication. Any process on the internal network could directly invoke agent execution, graph queries, or vector deletions without verification.
4. **Cascading Timeout Vulnerability (No Circuit Breaking):** When the AI service was saturated, restarting, or slow, HTTP proxy calls from `apps/api` blocked until Bun's default socket timeouts triggered, threatening thread and memory exhaustion on the gateway.

---

## Decision Drivers

- **Zero-Trust Seam:** The Python Intelligence Service must accept requests exclusively from the trusted Bun Control Plane. Direct or unsigned internal requests must be rejected immediately.
- **Strict Multi-Tenancy:** Multi-tenant boundaries are inviolable. If a repository cannot be verified or the requesting user is not a member of the project/organization, requests must fail fast with HTTP 403 Forbidden. Default tenant fallbacks (`"default"`) are strictly disallowed.
- **Fail-Fast Gateway Resiliency:** Downstream AI service outages must trip a circuit breaker immediately, returning clean HTTP 503 Service Unavailable responses instead of hanging upstream client connections.
- **Replay Protection:** Internal service authentication must guard against replay attacks and token forgery using timestamp-bounded HMAC-SHA256 signatures.

---

## Considered Options

1. **Option 1: Mount Auth in Hono Only and Use Static Internal API Key**
   - *Pros:* Simple to implement.
   - *Cons:* Static bearer tokens lack replay protection and time drift validation. Does not provide circuit breaking or strict RBAC tenancy validation.

2. **Option 2: Comprehensive Multi-Tier Security Seam & Circuit Breaker (Selected)**
   - Protect all functional intelligence routes in `apps/api` with `authMiddleware` while keeping `/health` open for container orchestrator probes.
   - Enforce strict RBAC in `verifyAndEnrichTenancy` via `getProjectForUser(user, projectId)`.
   - Implement an HMAC-SHA256 signature scheme (`X-Gitami-Internal-Auth: <timestamp>.<signature>`) using shared `INTERNAL_API_SECRET` and a 60-second replay window.
   - Mount `InternalServiceAuthMiddleware` in FastAPI to enforce HMAC validation across all intelligence routes while permitting health/doc endpoints.
   - Wrap gateway calls in an in-memory `CircuitBreaker` (5 consecutive failures -> OPEN for 15s -> HALF_OPEN probe -> HTTP 503).

---

## Decision Outcome

We selected **Option 2**. The implementation is divided into four tracer-bullet tickets:

1. **Ticket 01: Mount Gateway Auth Middleware & Strict Tenancy Verification**
   - Mount `authMiddleware` on all `/api/intelligence/*` routes (except `/health`) in `apps/api/src/modules/intelligence/intelligence.routes.ts`.
   - Replace loose `enrichPayloadWithTenancy` with strict `verifyAndEnrichTenancy`: lookup repository, verify user membership via `getProjectForUser(user, repo.projectId)`, inject `project_id`, `team_id`, `user_id`, and throw HTTP 403 on authorization failure.

2. **Ticket 02: Gateway Internal Token Signer & AI Client Wrapper**
   - Implement `signInternalServiceToken()` in `apps/api/src/utils/internal-auth.ts` generating `<timestamp>.<signature>` HMAC-SHA256 tokens using `INTERNAL_API_SECRET`.
   - Ensure environment configuration in `apps/api/src/configs/env.ts` defines `INTERNAL_API_SECRET`.
   - Update intelligence route fetch invocations to include `X-Gitami-Internal-Auth`.

3. **Ticket 03: FastAPI Internal Service Authentication Middleware**
   - Implement `InternalServiceAuthMiddleware` in `apps/ai/src/web/middleware/internal_auth.py`.
   - Verify `X-Gitami-Internal-Auth` header signature against `settings.internal_api_secret` and validate that `|now - timestamp| <= 60000ms`.
   - Whitelist open endpoints: `/api/health`, `/health`, `/docs`, `/openapi.json`.
   - Mount middleware in `apps/ai/src/web/app.py` and provide hermetic unit tests.

4. **Ticket 04: Circuit Breaker Guard for AI Service Proxy**
   - Implement `CircuitBreaker` in `apps/api/src/utils/circuit-breaker.ts` (threshold: 5 failures, recovery: 15,000ms).
   - Wrap outbound fetch calls in `intelligence.routes.ts` with `aiCircuitBreaker.execute(...)`.
   - Add unit tests verifying state transitions (`CLOSED` -> `OPEN` -> `HALF_OPEN` -> `CLOSED`) and HTTP 503 handling.

---

## Consequences & Security Impact

- **Positive:**
  - Completely blocks unauthenticated public access to the AI intelligence APIs.
  - Guarantees strict cross-tenant isolation in Neo4j and ChromaDB by ensuring all project and team IDs are cryptographically and relationally validated before reaching `apps/ai`.
  - Protects internal services from forged requests or lateral movement inside container networks.
  - Prevents gateway hanging during AI service degradation via circuit breaking.
- **Negative / Operational Needs:**
  - `INTERNAL_API_SECRET` must be set in production environments (defaults provided for development/test).
  - Clock synchronization (NTP) between `apps/api` and `apps/ai` containers must be maintained within the 60-second window.
