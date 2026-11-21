import { describe, it, expect, mock, beforeEach } from "bun:test";
import { CircuitBreaker, CircuitBreakerOpenError, aiCircuitBreaker } from "./circuit-breaker";

describe("CircuitBreaker", () => {
  describe("Slice 1: CLOSED State Execution", () => {
    it("executes the provided action and returns its result when CLOSED", async () => {
      const breaker = new CircuitBreaker();
      expect(breaker.getState()).toBe("CLOSED");

      const result = await breaker.execute(async () => "success-payload");
      expect(result).toBe("success-payload");
      expect(breaker.getState()).toBe("CLOSED");
      expect(breaker.getFailureCount()).toBe(0);
    });

    it("resets consecutive failure counter on a successful execution", async () => {
      let currentTime = 1000;
      const breaker = new CircuitBreaker({
        failureThreshold: 5,
        now: () => currentTime,
      });

      // Fail twice
      await expect(breaker.execute(async () => { throw new Error("fail 1"); })).rejects.toThrow("fail 1");
      await expect(breaker.execute(async () => { throw new Error("fail 2"); })).rejects.toThrow("fail 2");
      expect(breaker.getFailureCount()).toBe(2);
      expect(breaker.getState()).toBe("CLOSED");

      // Succeed once
      const res = await breaker.execute(async () => "ok");
      expect(res).toBe("ok");
      expect(breaker.getFailureCount()).toBe(0);
      expect(breaker.getState()).toBe("CLOSED");
    });
  });

  describe("Slice 2: Tripping from CLOSED to OPEN on Failure Threshold", () => {
    it("transitions state to OPEN after reaching 5 consecutive failures", async () => {
      let currentTime = 1000;
      const breaker = new CircuitBreaker({
        failureThreshold: 5,
        recoveryTimeoutMs: 15_000,
        now: () => currentTime,
      });

      for (let i = 1; i <= 4; i++) {
        await expect(breaker.execute(async () => { throw new Error(`error ${i}`); })).rejects.toThrow();
        expect(breaker.getState()).toBe("CLOSED");
        expect(breaker.getFailureCount()).toBe(i);
      }

      // 5th failure trips the breaker to OPEN
      await expect(breaker.execute(async () => { throw new Error("error 5"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");
      expect(breaker.getFailureCount()).toBe(5);
    });

    it("respects custom failure threshold configuration", async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 2 });
      await expect(breaker.execute(async () => { throw new Error("1"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("CLOSED");

      await expect(breaker.execute(async () => { throw new Error("2"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");
    });
  });

  describe("Slice 3: Fast Failure in OPEN State (HTTP 503)", () => {
    it("immediately throws CircuitBreakerOpenError with HTTP 503 without executing action", async () => {
      let currentTime = 1000;
      const breaker = new CircuitBreaker({
        failureThreshold: 2,
        recoveryTimeoutMs: 15_000,
        now: () => currentTime,
      });

      // Trip the breaker
      await expect(breaker.execute(async () => { throw new Error("1"); })).rejects.toThrow();
      await expect(breaker.execute(async () => { throw new Error("2"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");

      // Advance time slightly (within recovery window: 5,000ms < 15,000ms)
      currentTime += 5000;

      let actionCalled = false;
      const action = async () => {
        actionCalled = true;
        return "should-not-run";
      };

      try {
        await breaker.execute(action);
        expect.unreachable("Should have thrown CircuitBreakerOpenError");
      } catch (err: any) {
        expect(err).toBeInstanceOf(CircuitBreakerOpenError);
        expect(err.status).toBe(503);
        expect(err.message).toContain("circuit breaker is OPEN");
        const res = err.getResponse();
        expect(res.status).toBe(503);
        const data = await res.json();
        expect(data.error).toContain("circuit breaker is OPEN");
      }

      expect(actionCalled).toBe(false);
      expect(breaker.getState()).toBe("OPEN");
    });
  });

  describe("Slice 4: Recovery Window and HALF_OPEN State Transitions", () => {
    it("transitions from OPEN to HALF_OPEN after recovery window (15,000ms)", async () => {
      let currentTime = 1000;
      const breaker = new CircuitBreaker({
        failureThreshold: 2,
        recoveryTimeoutMs: 15_000,
        now: () => currentTime,
      });

      // Trip to OPEN
      await expect(breaker.execute(async () => { throw new Error("1"); })).rejects.toThrow();
      await expect(breaker.execute(async () => { throw new Error("2"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");

      // Advance time past recoveryTimeoutMs (15,001ms)
      currentTime += 15_001;

      // Next execution probes the downstream service in HALF_OPEN
      let observedStateDuringExecution = "";
      const result = await breaker.execute(async () => {
        observedStateDuringExecution = breaker.getState();
        return "probe-success";
      });

      expect(observedStateDuringExecution).toBe("HALF_OPEN");
      expect(result).toBe("probe-success");
      // On success, state resets to CLOSED and failure count to 0
      expect(breaker.getState()).toBe("CLOSED");
      expect(breaker.getFailureCount()).toBe(0);
    });

    it("trips back to OPEN if probe execution fails while in HALF_OPEN", async () => {
      let currentTime = 1000;
      const breaker = new CircuitBreaker({
        failureThreshold: 2,
        recoveryTimeoutMs: 15_000,
        now: () => currentTime,
      });

      // Trip to OPEN
      await expect(breaker.execute(async () => { throw new Error("1"); })).rejects.toThrow();
      await expect(breaker.execute(async () => { throw new Error("2"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");

      // Advance time past recovery window
      currentTime += 15_000;

      // Probe fails
      await expect(breaker.execute(async () => {
        expect(breaker.getState()).toBe("HALF_OPEN");
        throw new Error("probe failed");
      })).rejects.toThrow("probe failed");

      // Trips immediately back to OPEN
      expect(breaker.getState()).toBe("OPEN");

      // Immediate subsequent call is blocked by OPEN circuit
      let probe2Ran = false;
      await expect(breaker.execute(async () => {
        probe2Ran = true;
        return "fail";
      })).rejects.toThrow(CircuitBreakerOpenError);
      expect(probe2Ran).toBe(false);

      // Advance time again past recovery window: probes again
      currentTime += 15_000;
      const res2 = await breaker.execute(async () => "recovered");
      expect(res2).toBe("recovered");
      expect(breaker.getState()).toBe("CLOSED");
    });

    it("rejects concurrent requests while a probe is in flight during HALF_OPEN", async () => {
      let currentTime = 1000;
      const breaker = new CircuitBreaker({
        failureThreshold: 1,
        recoveryTimeoutMs: 15_000,
        now: () => currentTime,
      });

      // Trip to OPEN
      await expect(breaker.execute(async () => { throw new Error("1"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");

      // Advance time past recovery window
      currentTime += 15_000;

      // Start an in-flight probe that hasn't completed yet
      let resolveProbe: (val: string) => void = () => {};
      const probePromise = breaker.execute(() => new Promise<string>((res) => { resolveProbe = res; }));

      // Concurrent request arrives while probe is in flight
      await expect(breaker.execute(async () => "concurrent")).rejects.toThrow(CircuitBreakerOpenError);

      // Complete probe
      resolveProbe("done");
      const probeResult = await probePromise;
      expect(probeResult).toBe("done");
      expect(breaker.getState()).toBe("CLOSED");
    });
  });

  describe("Slice 5: Reset & Exported aiCircuitBreaker Singleton", () => {
    beforeEach(() => {
      aiCircuitBreaker.reset();
    });

    it("reset() forces state to CLOSED and failure count to 0", async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 2 });
      await expect(breaker.execute(async () => { throw new Error("1"); })).rejects.toThrow();
      await expect(breaker.execute(async () => { throw new Error("2"); })).rejects.toThrow();
      expect(breaker.getState()).toBe("OPEN");
      expect(breaker.getFailureCount()).toBe(2);

      breaker.reset();
      expect(breaker.getState()).toBe("CLOSED");
      expect(breaker.getFailureCount()).toBe(0);

      const res = await breaker.execute(async () => "alive");
      expect(res).toBe("alive");
    });

    it("provides the aiCircuitBreaker singleton instance with configured defaults", async () => {
      expect(aiCircuitBreaker).toBeInstanceOf(CircuitBreaker);
      expect(aiCircuitBreaker.getState()).toBe("CLOSED");
      expect(aiCircuitBreaker.getFailureCount()).toBe(0);

      // Execute 4 failures: remains CLOSED
      for (let i = 1; i <= 4; i++) {
        await expect(aiCircuitBreaker.execute(async () => { throw new Error(`fail ${i}`); })).rejects.toThrow();
        expect(aiCircuitBreaker.getState()).toBe("CLOSED");
        expect(aiCircuitBreaker.getFailureCount()).toBe(i);
      }

      // 5th failure trips aiCircuitBreaker to OPEN
      await expect(aiCircuitBreaker.execute(async () => { throw new Error("fail 5"); })).rejects.toThrow();
      expect(aiCircuitBreaker.getState()).toBe("OPEN");

      // Fast-fails with CircuitBreakerOpenError
      await expect(aiCircuitBreaker.execute(async () => new Response("should-fail"))).rejects.toThrow(CircuitBreakerOpenError);

      // Reset works
      aiCircuitBreaker.reset();
      expect(aiCircuitBreaker.getState()).toBe("CLOSED");
    });

    it("trips aiCircuitBreaker to OPEN on consecutive HTTP 5xx responses via isFailure predicate", async () => {
      expect(aiCircuitBreaker.getState()).toBe("CLOSED");

      // 5 consecutive 503 Service Unavailable responses from downstream
      for (let i = 1; i <= 5; i++) {
        const response = await aiCircuitBreaker.execute(async () =>
          new Response(JSON.stringify({ error: "Downstream overloaded" }), { status: 503 })
        );
        expect(response.status).toBe(503);
      }

      // 5 consecutive 5xx errors tripped breaker to OPEN
      expect(aiCircuitBreaker.getState()).toBe("OPEN");

      // Next execution fast-fails without executing action
      let actionCalled = false;
      await expect(aiCircuitBreaker.execute(async () => {
        actionCalled = true;
        return new Response("ok", { status: 200 });
      })).rejects.toThrow(CircuitBreakerOpenError);

      expect(actionCalled).toBe(false);
    });
  });
});
