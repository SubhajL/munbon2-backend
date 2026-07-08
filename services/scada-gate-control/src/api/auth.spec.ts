import jwt from 'jsonwebtoken';
import { describe, expect, test } from 'vitest';
import { AuthError, JwtTokenVerifier, mapAppRole } from './auth';
import type { Role } from '../domain/write-safety';

const SECRET = 'test-secret';
const ISSUER = 'munbon-auth';
const AUDIENCE = 'munbon-api';

const verifier = new JwtTokenVerifier({ secret: SECRET, issuer: ISSUER, audience: AUDIENCE });

function sign(payload: object, options: jwt.SignOptions = {}): string {
  return jwt.sign(payload, SECRET, {
    issuer: ISSUER,
    audience: AUDIENCE,
    expiresIn: '5m',
    ...options,
  });
}

describe('mapAppRole', () => {
  test.each<[string[], Role]>([
    [['rid_admin'], 'admin'],
    [['super_admin'], 'admin'],
    [['zone_manager'], 'operator'],
    [['guest'], 'viewer'],
    [['farmer_basic'], 'viewer'],
    [[], 'viewer'],
  ])('roles %j -> %s', (roleNames, expected) => {
    expect(mapAppRole(roleNames)).toBe(expected);
  });

  test('grants the highest privilege when several roles are present', () => {
    expect(mapAppRole(['guest', 'zone_manager', 'rid_admin'])).toBe('admin');
  });
});

describe('JwtTokenVerifier.verify', () => {
  test('decodes a valid access token and maps its role', () => {
    const token = sign({
      sub: 'user-1',
      email: 'op@rid.go.th',
      roles: ['zone_manager'],
      type: 'access',
    });
    expect(verifier.verify(token)).toEqual({
      userId: 'user-1',
      email: 'op@rid.go.th',
      roleNames: ['zone_manager'],
      role: 'operator',
    });
  });

  test('rejects a refresh token', () => {
    const token = sign({ sub: 'u', roles: ['rid_admin'], type: 'refresh' });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });

  test('rejects a token signed with a different secret', () => {
    const token = jwt.sign({ sub: 'u', roles: [], type: 'access' }, 'other-secret', {
      issuer: ISSUER,
      audience: AUDIENCE,
      expiresIn: '5m',
    });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });

  test('rejects a token with the wrong audience', () => {
    const token = sign({ sub: 'u', roles: [], type: 'access' }, { audience: 'someone-else' });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });

  test('rejects an expired token', () => {
    const token = sign({ sub: 'u', roles: [], type: 'access' }, { expiresIn: -10 });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });

  test('treats a token with no roles as viewer', () => {
    const token = sign({ sub: 'u', email: 'v@x', roles: [], type: 'access' });
    expect(verifier.verify(token).role).toBe('viewer');
  });

  test('rejects a token with the wrong issuer', () => {
    const token = sign({ sub: 'u', roles: [], type: 'access' }, { issuer: 'evil-issuer' });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });

  test("rejects an alg:'none' (unsigned) token", () => {
    const token = jwt.sign({ sub: 'u', roles: [], type: 'access' }, '', {
      algorithm: 'none',
      issuer: ISSUER,
      audience: AUDIENCE,
      expiresIn: '5m',
    });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });

  test('rejects a token with no expiry claim', () => {
    const token = jwt.sign({ sub: 'u', roles: [], type: 'access' }, SECRET, {
      issuer: ISSUER,
      audience: AUDIENCE,
      noTimestamp: true,
    });
    expect(() => verifier.verify(token)).toThrow(AuthError);
  });
});
