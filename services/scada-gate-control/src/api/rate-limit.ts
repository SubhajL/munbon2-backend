/**
 * In-memory sliding-window rate limiter for command endpoints, so a valid (or
 * stolen) operator token cannot hammer actuator writes. Keyed per user+gate.
 */
import type { NextFunction, Request, Response } from 'express';

export type RateLimitConfig = {
  readonly windowMs: number;
  readonly max: number;
};

export class SlidingWindowRateLimiter {
  private readonly hits = new Map<string, number[]>();

  constructor(
    private readonly config: RateLimitConfig,
    private readonly now: () => number = () => Date.now(),
  ) {}

  /** Records a hit and returns true if it is within the limit, false if over. */
  check(key: string): boolean {
    const cutoff = this.now() - this.config.windowMs;
    const recent = (this.hits.get(key) ?? []).filter((time) => time > cutoff);
    if (recent.length >= this.config.max) {
      this.hits.set(key, recent);
      return false;
    }
    recent.push(this.now());
    this.hits.set(key, recent);
    return true;
  }
}

export function commandRateLimit(
  limiter: SlidingWindowRateLimiter,
  keyOf: (req: Request) => string,
) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!limiter.check(keyOf(req))) {
      res.status(429).json({ error: 'too many commands, slow down' });
      return;
    }
    next();
  };
}
