import { describe, expect, test } from 'vitest';
import { CommandService, type CommandServiceDeps } from './command-service';
import { InMemoryAuditRepository } from '../audit/memory-repository';
import type { GateActuator, WriteExecution } from '../state/gate-controller';
import { buildSnapshot, emptyState, recordPoll, type GateSnapshot } from '../state/store';
import type { ModbusWrite } from '../domain/command';
import type { FreshnessThresholds } from '../state/freshness';
import type { PointReads } from '../transport/types';
import type { AuthenticatedUser } from '../api/auth';

const thresholds: FreshnessThresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const NOW = 1_700_000_000_000;
const okReads: PointReads = { gateLevel: 1, doorSw: 1, horn: 0, gateCf: 0 };

const snapshotFrom = (reads: PointReads, atMs: number, nowMs: number): GateSnapshot =>
  buildSnapshot(recordPoll(emptyState(), { ok: true, atMs, reads }), nowMs, thresholds);

const okSnapshot = snapshotFrom(okReads, 1_000, 1_000);
const staleSnapshot = snapshotFrom(okReads, 1_000, 12_000);

const operator: AuthenticatedUser = {
  userId: 'u1',
  email: 'op@rid.go.th',
  roleNames: ['zone_manager'],
  role: 'operator',
};
const viewer: AuthenticatedUser = { ...operator, roleNames: ['guest'], role: 'viewer' };

/** Fake actuator: returns a configurable snapshot + execution result, records calls. */
function fakeActuator(opts: {
  snapshot: GateSnapshot;
  execution?: (writes: readonly ModbusWrite[]) => WriteExecution;
}) {
  const calls: ModbusWrite[][] = [];
  const actuator: GateActuator = {
    snapshot: () => opts.snapshot,
    executeWrites: async (writes) => {
      calls.push([...writes]);
      return opts.execution
        ? opts.execution(writes)
        : { succeeded: writes, failed: null, snapshot: opts.snapshot };
    },
  };
  return { actuator, calls };
}

function makeService(actuator: GateActuator): {
  service: CommandService;
  audit: InMemoryAuditRepository;
} {
  const audit = new InMemoryAuditRepository();
  const deps: CommandServiceDeps = {
    actuator,
    audit,
    now: () => NOW,
    endpoint: { host: '172.16.1.103', port: 502, unitId: 1 },
    site: { gateId: 'waste-way', name: 'Waste Way' },
  };
  return { service: new CommandService(deps), audit };
}

describe('CommandService.commandGateLevel', () => {
  test('accepts a valid operator command, executes both writes, and audits ok', async () => {
    const reached = snapshotFrom({ ...okReads, gateLevel: 2 }, 2_000, 2_000);
    const { actuator, calls } = fakeActuator({
      snapshot: okSnapshot,
      execution: (writes) => ({ succeeded: writes, failed: null, snapshot: reached }),
    });
    const { service, audit } = makeService(actuator);

    const outcome = await service.commandGateLevel(operator, 2, true);

    expect(outcome).toEqual({ status: 'accepted', pending: false, snapshot: reached });
    expect(calls[0]).toEqual([
      { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: 2 },
      { kind: 'writeCoil', point: 'GateCF', address: 17, value: 1 },
    ]);
    expect(audit.entries).toEqual([
      {
        timestamp: new Date(NOW).toISOString(),
        userId: 'u1',
        userRole: 'operator',
        gateId: 'waste-way',
        gateName: 'Waste Way',
        commandType: 'command-level',
        requestedTarget: 2,
        modbusHost: '172.16.1.103',
        modbusPort: 502,
        unitId: 1,
        writes: [
          { address: 108, value: 2 },
          { address: 17, value: 1 },
        ],
        result: 'ok',
        error: null,
      },
    ]);
  });

  test('reports pending=true when the read-back has not reached the target', async () => {
    const { actuator } = fakeActuator({
      snapshot: okSnapshot,
      execution: (writes) => ({ succeeded: writes, failed: null, snapshot: okSnapshot }),
    });
    const { service } = makeService(actuator);
    expect(await service.commandGateLevel(operator, 2, true)).toMatchObject({
      status: 'accepted',
      pending: true,
    });
  });

  test.each<[string, AuthenticatedUser, number, boolean, GateSnapshot, string]>([
    ['viewer role', viewer, 2, true, okSnapshot, 'role_forbidden'],
    ['stale data', operator, 2, true, staleSnapshot, 'data_stale'],
    ['not confirmed', operator, 2, false, okSnapshot, 'not_confirmed'],
    ['invalid target', operator, 9, true, okSnapshot, 'invalid_target'],
  ])(
    'rejects %s without actuating, and audits the rejection',
    async (_l, user, target, confirmed, snap, reason) => {
      const { actuator, calls } = fakeActuator({ snapshot: snap });
      const { service, audit } = makeService(actuator);

      const outcome = await service.commandGateLevel(user, target, confirmed);

      expect(outcome).toMatchObject({ status: 'rejected', reason });
      expect(calls).toEqual([]); // no actuation attempted
      expect(audit.entries).toMatchObject([{ result: 'rejected', writes: [] }]);
    },
  );

  test('on partial write failure, audits the attempted writes (succeeded + failed) with error', async () => {
    const failed = {
      succeeded: [
        { kind: 'writeHoldingRegister', point: 'Op_gate', address: 108, value: 2 },
      ] as ModbusWrite[],
      failed: {
        write: { kind: 'writeCoil', point: 'GateCF', address: 17, value: 1 } as ModbusWrite,
        error: 'coil write failed',
      },
      snapshot: okSnapshot,
    };
    const { actuator } = fakeActuator({ snapshot: okSnapshot, execution: () => failed });
    const { service, audit } = makeService(actuator);

    const outcome = await service.commandGateLevel(operator, 2, true);

    expect(outcome).toMatchObject({ status: 'error', error: 'coil write failed' });
    expect(audit.entries).toMatchObject([
      {
        result: 'error',
        error: 'coil write failed',
        writes: [
          { address: 108, value: 2 },
          { address: 17, value: 1 },
        ],
      },
    ]);
  });
});

describe('CommandService.commandHorn', () => {
  test('accepts an operator horn-on command and audits the coil write', async () => {
    const hornOn = snapshotFrom({ ...okReads, horn: 1 }, 2_000, 2_000);
    const { actuator, calls } = fakeActuator({
      snapshot: okSnapshot,
      execution: (writes) => ({ succeeded: writes, failed: null, snapshot: hornOn }),
    });
    const { service, audit } = makeService(actuator);

    const outcome = await service.commandHorn(operator, true, true);

    expect(outcome).toMatchObject({ status: 'accepted', pending: false });
    expect(calls[0]).toEqual([{ kind: 'writeCoil', point: 'Horn', address: 15, value: 1 }]);
    expect(audit.entries).toMatchObject([
      {
        commandType: 'horn',
        requestedTarget: true,
        writes: [{ address: 15, value: 1 }],
        result: 'ok',
      },
    ]);
  });

  test('rejects a viewer horn command without actuating', async () => {
    const { actuator, calls } = fakeActuator({ snapshot: okSnapshot });
    const { service } = makeService(actuator);
    expect(await service.commandHorn(viewer, true, true)).toMatchObject({
      status: 'rejected',
      reason: 'role_forbidden',
    });
    expect(calls).toEqual([]);
  });
});
