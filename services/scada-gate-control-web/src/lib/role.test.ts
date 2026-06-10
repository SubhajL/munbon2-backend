import { describe, expect, test } from 'vitest';
import { canCommand, mapAppRole, roleFromToken, type AppRole } from './role';

const fakeJwt = (payload: object): string => {
  const b64url = (obj: object) =>
    Buffer.from(JSON.stringify(obj)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${b64url({ alg: 'HS256' })}.${b64url(payload)}.sig`;
};

describe('mapAppRole', () => {
  test.each<[string[], AppRole]>([
    [['rid_admin'], 'admin'],
    [['zone_manager'], 'operator'],
    [['guest'], 'viewer'],
    [['guest', 'rid_admin'], 'admin'],
  ])('%j -> %s', (roles, expected) => {
    expect(mapAppRole(roles)).toBe(expected);
  });
});

describe('canCommand', () => {
  test.each<[AppRole, boolean]>([
    ['viewer', false],
    ['operator', true],
    ['admin', true],
  ])('%s -> %s', (role, expected) => {
    expect(canCommand(role)).toBe(expected);
  });
});

describe('roleFromToken', () => {
  test('derives the app role from a JWT roles claim', () => {
    expect(roleFromToken(fakeJwt({ sub: 'u', roles: ['zone_manager'], type: 'access' }))).toBe('operator');
  });

  test('returns viewer for a missing or malformed token', () => {
    expect(roleFromToken(undefined)).toBe('viewer');
    expect(roleFromToken('not-a-jwt')).toBe('viewer');
  });
});
