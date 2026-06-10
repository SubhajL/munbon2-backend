import { describe, expect, test } from 'vitest';
import { planGateLevelCommand, planHornCommand } from './plan';
import type { CommandWriteContext } from './write-safety';

const operatorOk: CommandWriteContext = {
  authenticated: true,
  role: 'operator',
  quality: 'ok',
  confirmed: true,
};

describe('planGateLevelCommand', () => {
  test('builds the gate writes only when safety passes', () => {
    expect(planGateLevelCommand({ ...operatorOk, targetValue: 2 })).toEqual({
      allowed: true,
      writes: [
        { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: 2 },
        { kind: 'writeCoil', point: 'GateCF', address: 17, value: 1 },
      ],
    });
  });

  // A denied plan must surface the reason AND emit no writes (no actuation).
  test.each<[string, Partial<CommandWriteContext & { targetValue: number }>, string]>([
    ['viewer', { role: 'viewer' }, 'role_forbidden'],
    ['stale', { quality: 'stale' }, 'data_stale'],
    ['unconfirmed', { confirmed: false }, 'not_confirmed'],
    ['bad target', { targetValue: 9 }, 'invalid_target'],
  ])('denies %s and produces no writes', (_label, override, reason) => {
    const plan = planGateLevelCommand({ ...operatorOk, targetValue: 2, ...override });
    expect(plan).toEqual({ allowed: false, reason });
    expect('writes' in plan).toBe(false);
  });
});

describe('planHornCommand', () => {
  test('builds the horn write when safety passes (enabled)', () => {
    expect(planHornCommand({ ...operatorOk, enabled: true })).toEqual({
      allowed: true,
      writes: [{ kind: 'writeCoil', point: 'Horn', address: 15, value: 1 }],
    });
  });

  test('builds the off write when disabled', () => {
    expect(planHornCommand({ ...operatorOk, enabled: false })).toEqual({
      allowed: true,
      writes: [{ kind: 'writeCoil', point: 'Horn', address: 15, value: 0 }],
    });
  });

  test('denies a viewer and emits no writes', () => {
    const plan = planHornCommand({ ...operatorOk, role: 'viewer', enabled: true });
    expect(plan).toEqual({ allowed: false, reason: 'role_forbidden' });
    expect('writes' in plan).toBe(false);
  });
});
