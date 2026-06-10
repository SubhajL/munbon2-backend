import { describe, expect, test } from 'vitest';
import {
  canCommand,
  evaluateGateLevelWriteSafety,
  evaluateHornWriteSafety,
  type CommandWriteContext,
  type Role,
} from './write-safety';

const gateOk: CommandWriteContext & { targetValue: number } = {
  authenticated: true,
  role: 'operator',
  quality: 'ok',
  confirmed: true,
  targetValue: 2,
};

const hornOk: CommandWriteContext = {
  authenticated: true,
  role: 'operator',
  quality: 'ok',
  confirmed: true,
};

// Shared deny cases: each overrides exactly one field of a valid context to
// isolate a single rule, in the spec's precedence order.
const commonDenyCases: ReadonlyArray<[string, Partial<CommandWriteContext>, string]> = [
  ['unauthenticated', { authenticated: false }, 'not_authenticated'],
  ['viewer role', { role: 'viewer' }, 'role_forbidden'],
  ['stale data', { quality: 'stale' }, 'data_stale'],
  ['offline data', { quality: 'offline' }, 'data_offline'],
  ['modbus exception', { quality: 'modbus_exception' }, 'data_unavailable'],
  ['decode error', { quality: 'decode_error' }, 'data_unavailable'],
  ['not confirmed', { confirmed: false }, 'not_confirmed'],
];

describe('canCommand', () => {
  test.each<[Role, boolean]>([
    ['viewer', false],
    ['operator', true],
    ['admin', true],
  ])('role %s -> %s', (role, expected) => {
    expect(canCommand(role)).toBe(expected);
  });
});

describe('evaluateGateLevelWriteSafety', () => {
  test.each([1, 2, 3, 4] as const)(
    'allows a valid operator command and echoes target %i',
    (target) => {
      expect(evaluateGateLevelWriteSafety({ ...gateOk, targetValue: target })).toEqual({
        allowed: true,
        target,
      });
    },
  );

  test('allows an admin to command as well', () => {
    expect(evaluateGateLevelWriteSafety({ ...gateOk, role: 'admin' })).toEqual({
      allowed: true,
      target: 2,
    });
  });

  test.each([
    ...commonDenyCases,
    ['target 0', { targetValue: 0 }, 'invalid_target'],
    ['target 5', { targetValue: 5 }, 'invalid_target'],
  ] as ReadonlyArray<[string, Partial<CommandWriteContext & { targetValue: number }>, string]>)(
    'denies %s with reason %s',
    (_label, override, reason) => {
      expect(evaluateGateLevelWriteSafety({ ...gateOk, ...override })).toEqual({
        allowed: false,
        reason,
      });
    },
  );

  test('reports the earliest failing check (auth before role)', () => {
    expect(
      evaluateGateLevelWriteSafety({ ...gateOk, authenticated: false, role: 'viewer' }),
    ).toEqual({ allowed: false, reason: 'not_authenticated' });
  });

  test('confirmation is checked before target validity (spec order)', () => {
    expect(evaluateGateLevelWriteSafety({ ...gateOk, confirmed: false, targetValue: 99 })).toEqual({
      allowed: false,
      reason: 'not_confirmed',
    });
  });
});

describe('evaluateHornWriteSafety', () => {
  test.each<[Role]>([['operator'], ['admin']])(
    'allows a valid %s horn command (no target needed)',
    (role) => {
      expect(evaluateHornWriteSafety({ ...hornOk, role })).toEqual({ allowed: true });
    },
  );

  test.each(commonDenyCases)('denies %s with reason %s', (_label, override, reason) => {
    expect(evaluateHornWriteSafety({ ...hornOk, ...override })).toEqual({
      allowed: false,
      reason,
    });
  });

  test('reports the earliest failing check (auth before role)', () => {
    expect(evaluateHornWriteSafety({ ...hornOk, authenticated: false, role: 'viewer' })).toEqual({
      allowed: false,
      reason: 'not_authenticated',
    });
  });
});
