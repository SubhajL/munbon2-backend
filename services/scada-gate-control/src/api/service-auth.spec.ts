import jwt from 'jsonwebtoken';
import { describe, expect, it } from 'vitest';

import {
  SchedulerServiceTokenVerifier,
  ServiceAuthError,
  verifySchedulerServiceToken,
} from './service-auth';

const SECRET = 'scheduler-service-secret-value';
const ISSUER = 'munbon-scheduler';
const AUDIENCE = 'munbon-scada-machine-boundary';
const CONFIG = { secret: SECRET, issuer: ISSUER, audience: AUDIENCE, maxAge: '5m' };

function sign(payload: object, options: jwt.SignOptions = {}, secret = SECRET): string {
  return jwt.sign(payload, secret, {
    issuer: ISSUER,
    audience: AUDIENCE,
    expiresIn: '5m',
    ...options,
  });
}

describe('verifySchedulerServiceToken', () => {
  it('accepts a well-formed short-lived service token and returns its subject', () => {
    const token = sign({ sub: 'svc:scheduler', type: 'service' });
    expect(verifySchedulerServiceToken(token, CONFIG)).toEqual({ subject: 'svc:scheduler' });
  });

  it('rejects a token whose audience is not the machine-boundary audience', () => {
    const token = sign({ sub: 'svc:scheduler', type: 'service' }, { audience: 'munbon-api' });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects an expired token (older than maxAge / past exp)', () => {
    const token = sign({ sub: 'svc:scheduler', type: 'service' }, { expiresIn: '-1m' });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a token older than maxAge even if exp is still in the future', () => {
    // iat 10m ago, exp 20m ahead: not exp-expired, but past the 5m maxAge.
    const issuedAt = Math.floor(Date.now() / 1000) - 600;
    const token = sign(
      { sub: 'svc:scheduler', type: 'service', iat: issuedAt },
      { expiresIn: '30m' },
    );
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a non-service token type (an operator access token cannot cross over)', () => {
    const token = sign({ sub: 'user-1', type: 'access', roles: ['zone_manager'] });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a token signed with a different secret', () => {
    const token = sign({ sub: 'svc:scheduler', type: 'service' }, {}, 'other-secret');
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a token from a different issuer', () => {
    const token = sign({ sub: 'svc:scheduler', type: 'service' }, { issuer: 'munbon-auth' });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a token with no subject', () => {
    const token = sign({ type: 'service' });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a token with a blank subject', () => {
    const token = sign({ sub: '   ', type: 'service' });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('rejects a service token with no expiry (a non-expiring token is refused)', () => {
    // No expiresIn => no exp claim; maxAge alone would pass on a fresh iat, so the
    // explicit exp-presence guard is what stops an eternal token.
    const token = jwt.sign({ sub: 'svc:scheduler', type: 'service' }, SECRET, {
      issuer: ISSUER,
      audience: AUDIENCE,
    });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('still enforces the 5m default when the configured maxAge is blank (no fail-open)', () => {
    const issuedAt = Math.floor(Date.now() / 1000) - 600; // 10m ago, exp still ahead
    const token = sign(
      { sub: 'svc:scheduler', type: 'service', iat: issuedAt },
      { expiresIn: '30m' },
    );
    expect(() => verifySchedulerServiceToken(token, { ...CONFIG, maxAge: '' })).toThrow(
      ServiceAuthError,
    );
  });

  it('rejects an alg=none unsigned token (HS256 is pinned)', () => {
    const token = jwt.sign({ sub: 'svc:scheduler', type: 'service' }, '', {
      algorithm: 'none',
      issuer: ISSUER,
      audience: AUDIENCE,
    });
    expect(() => verifySchedulerServiceToken(token, CONFIG)).toThrow(ServiceAuthError);
  });

  it('returns the execute scope and content bindings for a bound token', () => {
    const token = sign({
      sub: 'svc:scheduler',
      type: 'service',
      scope: 'command_intents.execute',
      jti: 'execute-1',
      grant_id: '77777777-7777-4777-8777-777777777777',
      authority_not_after: '2026-07-20T03:05:00.000Z',
      intent_id: '11111111-1111-1111-1111-111111111111',
      original_intent_content_hash: 'a'.repeat(64),
      execution_intent_content_hash: 'b'.repeat(64),
      purpose: 'operator_approved',
    });
    expect(verifySchedulerServiceToken(token, CONFIG)).toEqual({
      subject: 'svc:scheduler',
      scope: 'command_intents.execute',
      expiresAtMs: expect.any(Number),
      jti: 'execute-1',
      grantId: '77777777-7777-4777-8777-777777777777',
      authorityNotAfter: '2026-07-20T03:05:00.000Z',
      intentId: '11111111-1111-1111-1111-111111111111',
      originalIntentContentHash: 'a'.repeat(64),
      executionIntentContentHash: 'b'.repeat(64),
      purpose: 'operator_approved',
    });
  });
});

describe('SchedulerServiceTokenVerifier', () => {
  it('verifies via the class wrapper with the same policy', () => {
    const verifier = new SchedulerServiceTokenVerifier(CONFIG);
    const token = sign({ sub: 'svc:scheduler', type: 'service' });
    expect(verifier.verify(token)).toEqual({ subject: 'svc:scheduler' });
  });
});
