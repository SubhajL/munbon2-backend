import { createLogger } from '../logger';

const logger = createLogger('circuit-breaker');

export interface CircuitBreakerOptions {
  failureThreshold?: number;
  resetTimeout?: number;
  monitoringPeriod?: number;
  minimumRequests?: number;
  onOpen?: () => void;
  onClose?: () => void;
  onHalfOpen?: () => void;
}

enum State {
  CLOSED = 'CLOSED',
  OPEN = 'OPEN',
  HALF_OPEN = 'HALF_OPEN'
}

export class CircuitBreaker<T> {
  private state: State = State.CLOSED;
  private failures = 0;
  private successes = 0;
  private requests = 0;
  private nextAttempt: number = Date.now();
  private monitoringStart: number = Date.now();

  constructor(
    private readonly fn: (...args: any[]) => Promise<T>,
    private readonly options: CircuitBreakerOptions = {}
  ) {
    this.options = {
      failureThreshold: 50, // 50% failure rate
      resetTimeout: 60000, // 1 minute
      monitoringPeriod: 10000, // 10 seconds
      minimumRequests: 10,
      ...options
    };
  }

  async execute(...args: any[]): Promise<T> {
    if (this.state === State.OPEN) {
      if (Date.now() < this.nextAttempt) {
        throw new Error('Circuit breaker is OPEN');
      }
      this.state = State.HALF_OPEN;
      this.options.onHalfOpen?.();
      logger.info('Circuit breaker transitioned to HALF_OPEN');
    }

    try {
      const result = await this.fn(...args);
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess(): void {
    this.requests++;
    this.successes++;

    if (this.state === State.HALF_OPEN) {
      this.state = State.CLOSED;
      this.options.onClose?.();
      this.reset();
      logger.info('Circuit breaker transitioned to CLOSED');
    }

    this.checkMonitoringPeriod();
  }

  private onFailure(): void {
    this.requests++;
    this.failures++;

    if (this.state === State.HALF_OPEN) {
      this.state = State.OPEN;
      this.nextAttempt = Date.now() + this.options.resetTimeout!;
      this.options.onOpen?.();
      logger.warn('Circuit breaker transitioned to OPEN from HALF_OPEN');
      this.reset();
      return;
    }

    if (this.shouldOpen()) {
      this.state = State.OPEN;
      this.nextAttempt = Date.now() + this.options.resetTimeout!;
      this.options.onOpen?.();
      logger.warn('Circuit breaker transitioned to OPEN', {
        failures: this.failures,
        requests: this.requests,
        failureRate: this.getFailureRate()
      });
      this.reset();
    }

    this.checkMonitoringPeriod();
  }

  private shouldOpen(): boolean {
    if (this.requests < this.options.minimumRequests!) {
      return false;
    }
    return this.getFailureRate() >= this.options.failureThreshold!;
  }

  private getFailureRate(): number {
    if (this.requests === 0) return 0;
    return (this.failures / this.requests) * 100;
  }

  private checkMonitoringPeriod(): void {
    if (Date.now() - this.monitoringStart > this.options.monitoringPeriod!) {
      this.reset();
    }
  }

  private reset(): void {
    this.failures = 0;
    this.successes = 0;
    this.requests = 0;
    this.monitoringStart = Date.now();
  }

  getState(): State {
    return this.state;
  }

  getStats(): {
    state: State;
    failures: number;
    successes: number;
    requests: number;
    failureRate: number;
  } {
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes,
      requests: this.requests,
      failureRate: this.getFailureRate()
    };
  }
}