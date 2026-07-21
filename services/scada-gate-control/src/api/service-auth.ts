/**
 * PR 6.2 — Scheduler service-to-service authentication for the machine-boundary
 * validation endpoint. This is CRYPTOGRAPHICALLY SEPARATE from operator auth
 * (`auth.ts`): a distinct HS256 secret (`SCHEDULER_SERVICE_JWT_SECRET`), a distinct
 * audience pin, and a `type: 'service'` discriminator — so a leaked operator secret
 * cannot forge a service token and an operator access token cannot cross over.
 *
 * Short-lived by policy (`maxAge`, default 5m). Carries NO roles: a service is not an
 * operator, so there is no role mapping — only a verified `subject`.
 *
 * Read-only/validation routes require exact scopes. Physical execution additionally
 * requires a per-request jti and exact intent/hash/purpose bindings at the route.
 */
import type { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

import { extractBearerToken } from './middleware';

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      serviceAuth?: ServicePrincipal;
    }
  }
}

export class ServiceAuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ServiceAuthError';
  }
}

export type ServicePrincipal = {
  readonly subject: string;
  readonly scope?: string;
  readonly jti?: string;
  readonly expiresAtMs?: number;
  readonly grantId?: string;
  readonly authorityNotAfter?: string;
  readonly intentId?: string;
  readonly originalIntentContentHash?: string;
  readonly executionIntentContentHash?: string;
  readonly purpose?: string;
};

export type SchedulerServiceTokenConfig = {
  readonly secret: string;
  readonly issuer: string;
  readonly audience: string;
  /** Reject tokens older than this regardless of exp (defaults to 5m — "short-lived"). */
  readonly maxAge?: string;
};

export interface ServiceTokenVerifier {
  verify(token: string): ServicePrincipal;
}

/**
 * Verify a scheduler service token. Pins HS256 (no alg-confusion / `none`), the issuer,
 * the machine-boundary audience, a `type: 'service'` discriminator, a non-blank subject,
 * a present `exp`, and `maxAge`. Throws `ServiceAuthError` on any failure.
 */
export function verifySchedulerServiceToken(
  token: string,
  config: SchedulerServiceTokenConfig,
): ServicePrincipal {
  // Fail CLOSED on a blank maxAge: `?? '5m'` only catches undefined, but jsonwebtoken
  // SKIPS its max-age check for any falsy value (e.g. ''), which would silently disable
  // the short-lived-token policy. Treat empty/whitespace as "use the 5m default".
  const maxAge = config.maxAge && config.maxAge.trim() !== '' ? config.maxAge : '5m';
  let payload: jwt.JwtPayload | string;
  try {
    payload = jwt.verify(token, config.secret, {
      issuer: config.issuer,
      audience: config.audience,
      algorithms: ['HS256'], // pin HS256 — no alg-confusion / 'none'
      maxAge,
    });
  } catch {
    throw new ServiceAuthError('invalid or expired service token');
  }
  if (typeof payload === 'string') {
    throw new ServiceAuthError('unexpected token payload');
  }
  if (typeof payload.exp !== 'number') {
    throw new ServiceAuthError('service token missing expiry');
  }
  if (payload.type !== 'service') {
    throw new ServiceAuthError('not a service token');
  }
  if (typeof payload.sub !== 'string' || payload.sub.trim() === '') {
    throw new ServiceAuthError('service token missing subject');
  }
  const principal: ServicePrincipal = { subject: payload.sub };
  if (typeof payload.scope !== 'string') return principal;
  return {
    ...principal,
    scope: payload.scope,
    expiresAtMs: payload.exp * 1000,
    ...(typeof payload.jti === 'string' ? { jti: payload.jti } : {}),
    ...(typeof payload.grant_id === 'string' ? { grantId: payload.grant_id } : {}),
    ...(typeof payload.authority_not_after === 'string'
      ? { authorityNotAfter: payload.authority_not_after }
      : {}),
    ...(typeof payload.intent_id === 'string' ? { intentId: payload.intent_id } : {}),
    ...(typeof payload.original_intent_content_hash === 'string'
      ? { originalIntentContentHash: payload.original_intent_content_hash }
      : {}),
    ...(typeof payload.execution_intent_content_hash === 'string'
      ? { executionIntentContentHash: payload.execution_intent_content_hash }
      : {}),
    ...(typeof payload.purpose === 'string' ? { purpose: payload.purpose } : {}),
  };
}

export class SchedulerServiceTokenVerifier implements ServiceTokenVerifier {
  constructor(private readonly config: SchedulerServiceTokenConfig) {}

  verify(token: string): ServicePrincipal {
    return verifySchedulerServiceToken(token, this.config);
  }
}

/**
 * Express middleware guarding the machine-boundary endpoint. A `null` verifier (service
 * secret unset) fails CLOSED with 503 — the route stays mounted so its absence is never a
 * silent contract change, but it validates nothing until a service secret is configured.
 * On success attaches `req.serviceAuth`.
 */
export function requireServiceAuth(verifier: ServiceTokenVerifier | null) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (verifier === null) {
      res.status(503).json({ error: 'service auth not configured' });
      return;
    }
    const token = extractBearerToken(req);
    if (!token) {
      res.status(401).json({ error: 'missing service bearer token' });
      return;
    }
    try {
      req.serviceAuth = verifier.verify(token);
      next();
    } catch (error) {
      if (error instanceof ServiceAuthError) {
        res.status(401).json({ error: error.message });
        return;
      }
      next(error);
    }
  };
}

export function requireServiceScope(scope: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (req.serviceAuth?.scope !== scope) {
      res.status(403).json({ error: 'service token has the wrong scope' });
      return;
    }
    next();
  };
}
