export type CircuitBreakerState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface CircuitBreakerOptions<T = any> {
  failureThreshold?: number;
  recoveryTimeoutMs?: number;
  now?: () => number;
  isFailure?: (error: unknown, result?: T) => boolean;
}

export class CircuitBreakerOpenError extends Error {
  readonly status = 503;

  constructor(
    message = "Service Unavailable: Downstream AI service circuit breaker is OPEN",
  ) {
    super(message);
    this.name = "CircuitBreakerOpenError";
  }

  getResponse(): Response {
    return Response.json({ error: this.message }, { status: 503 });
  }
}

export class CircuitBreaker<T = any> {
  private state: CircuitBreakerState = "CLOSED";
  private failureCount = 0;
  private readonly failureThreshold: number;
  private readonly recoveryTimeoutMs: number;
  private readonly now: () => number;
  private readonly isFailure?: (error: unknown, result?: T) => boolean;
  private lastStateChange: number;

  constructor(options: CircuitBreakerOptions<T> = {}) {
    this.failureThreshold = options.failureThreshold ?? 5;
    this.recoveryTimeoutMs = options.recoveryTimeoutMs ?? 15_000;
    this.now = options.now ?? (() => Date.now());
    this.isFailure = options.isFailure;
    this.lastStateChange = this.now();
  }

  getState(): CircuitBreakerState {
    return this.state;
  }

  getFailureCount(): number {
    return this.failureCount;
  }

  reset(): void {
    this.state = "CLOSED";
    this.failureCount = 0;
    this.lastStateChange = this.now();
  }

  private recordSuccess(): void {
    this.state = "CLOSED";
    this.failureCount = 0;
  }

  private recordFailure(): void {
    if (this.state === "HALF_OPEN") {
      this.state = "OPEN";
      this.lastStateChange = this.now();
    } else {
      this.failureCount++;
      if (this.failureCount >= this.failureThreshold) {
        this.state = "OPEN";
        this.lastStateChange = this.now();
      }
    }
  }

  async execute<R = T>(action: () => Promise<R>): Promise<R> {
    if (this.state === "OPEN") {
      const elapsed = this.now() - this.lastStateChange;
      if (elapsed < this.recoveryTimeoutMs) {
        throw new CircuitBreakerOpenError();
      }
      this.state = "HALF_OPEN";
      this.lastStateChange = this.now();
    } else if (this.state === "HALF_OPEN") {
      // Reject concurrent requests while single probe is in flight
      throw new CircuitBreakerOpenError(
        "Service Unavailable: Downstream AI service circuit breaker is probing in HALF_OPEN",
      );
    }

    try {
      const result = await action();
      const isFailed = this.isFailure ? this.isFailure(null, result as any) : false;
      if (isFailed) {
        this.recordFailure();
      } else {
        this.recordSuccess();
      }
      return result;
    } catch (error) {
      this.recordFailure();
      throw error;
    }
  }
}

export const aiCircuitBreaker = new CircuitBreaker<Response>({
  failureThreshold: 5,
  recoveryTimeoutMs: 15_000,
  isFailure: (error, res) => {
    if (error) return true;
    if (res && res.status >= 500) return true;
    return false;
  },
});
