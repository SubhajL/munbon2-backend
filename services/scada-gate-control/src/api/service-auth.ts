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
 * Replay: a captured token is replayable for its (short) maxAge window. That is benign
 * for THIS endpoint because it is validation-only and idempotent on intent_content_hash
 * (a replay reproduces the same durable receipt, no side effect). Any future
 * NON-idempotent endpoint reusing this verifier MUST add nonce/jti anti-replay.
 */
import jwt from 'jsonwebtoken';

export class ServiceAuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ServiceAuthError';
  }
}

export type ServicePrincipal = {
  readonly subject: string;
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
  return { subject: payload.sub };
}

export class SchedulerServiceTokenVerifier implements ServiceTokenVerifier {
  constructor(private readonly config: SchedulerServiceTokenConfig) {}

  verify(token: string): ServicePrincipal {
    return verifySchedulerServiceToken(token, this.config);
  }
}
