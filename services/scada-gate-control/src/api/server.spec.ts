import jwt from 'jsonwebtoken';
import request from 'supertest';
import { describe, expect, test } from 'vitest';
import { buildServer } from './server';
import { JwtTokenVerifier } from './auth';
import { CommandService } from '../services/command-service';
import { emptyDeviceCapabilitySnapshot } from '../domain/device-registry';
import { InMemoryAuditRepository } from '../audit/memory-repository';
import { InMemoryCommandIntentReceiptRepository } from '../command-intents/memory-repository';
import { createScadaMetrics } from '../metrics/registry';
import type { GateActuator } from '../state/gate-controller';
import { buildSnapshot, emptyState, recordPoll, type GateSnapshot } from '../state/store';
import type { ModbusWrite } from '../domain/command';
import type { PointReads } from '../transport/types';

const generousRateLimit = { windowMs: 60_000, max: 100 };

const SECRET = 'test-secret';
const ISSUER = 'munbon-auth';
const AUDIENCE = 'munbon-api';
const thresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const site = { gateId: 'waste-way', name: 'Waste Way' };
const endpoint = { host: '172.16.1.103', port: 502, unitId: 1 };

const snapshotFrom = (reads: PointReads, atMs: number, nowMs: number): GateSnapshot =>
  buildSnapshot(recordPoll(emptyState(), { ok: true, atMs, reads }), nowMs, thresholds);

const okSnapshot = snapshotFrom({ gateLevel: 2, doorSw: 1, horn: 0, gateCf: 0 }, 1_000, 1_000);

const signToken = (roles: string[]): string =>
  jwt.sign({ sub: 'u1', email: 'x@rid.go.th', roles, type: 'access' }, SECRET, {
    issuer: ISSUER,
    audience: AUDIENCE,
    expiresIn: '5m',
  });

const operatorAuth = `Bearer ${signToken(['zone_manager'])}`;
const viewerAuth = `Bearer ${signToken(['guest'])}`;

function setup(rateLimit = generousRateLimit) {
  const writes: Array<{ kind: string; address: number; value: number | boolean }> = [];
  // Fake actuator records the writes a command would issue (serialization is
  // covered in gate-controller.spec); HTTP wiring is what this suite exercises.
  const actuator: GateActuator = {
    snapshot: () => okSnapshot,
    executeWrites: async (planned: readonly ModbusWrite[]) => {
      for (const write of planned) {
        if (write.kind === 'writeHoldingRegister') {
          writes.push({ kind: 'hr', address: write.address, value: write.value });
        } else {
          writes.push({ kind: 'coil', address: write.address, value: write.value === 1 });
        }
      }
      return { succeeded: planned, failed: null, snapshot: okSnapshot };
    },
  };
  const audit = new InMemoryAuditRepository();
  const commandService = new CommandService({
    actuator,
    audit,
    now: () => 1_700_000_000_000,
    endpoint,
    site,
  });
  const metrics = createScadaMetrics();
  const app = buildServer({
    verifier: new JwtTokenVerifier({ secret: SECRET, issuer: ISSUER, audience: AUDIENCE }),
    commandService,
    snapshot: () => okSnapshot,
    site,
    endpoint,
    rateLimit,
    deviceCapabilities: emptyDeviceCapabilitySnapshot(),
    serviceVerifier: null,
    receipts: new InMemoryCommandIntentReceiptRepository(),
    clock: () => 1_700_000_000_000,
    approvedLineageAnchor: null,
    siteCanonicalGateId: null,
    metrics,
  });
  return { app, writes, audit, metrics };
}

describe('GET /api/sites', () => {
  test('401 without a token', async () => {
    await request(setup().app).get('/api/sites').expect(401);
  });

  test('returns the site summary for an authenticated user', async () => {
    const res = await request(setup().app)
      .get('/api/sites')
      .set('authorization', viewerAuth)
      .expect(200);
    expect(res.body).toEqual([
      {
        id: 'waste-way',
        name: 'Waste Way',
        connection: 'ok',
        markerColor: 'green',
        lastUpdated: okSnapshot.lastUpdated,
      },
    ]);
  });
});

describe('GET /api/gates/:id/status', () => {
  test('returns the snapshot + endpoint for the known gate', async () => {
    const res = await request(setup().app)
      .get('/api/gates/waste-way/status')
      .set('authorization', viewerAuth)
      .expect(200);
    expect(res.body).toMatchObject({ id: 'waste-way', connection: 'ok', endpoint });
  });

  test('404 for an unknown gate id', async () => {
    await request(setup().app)
      .get('/api/gates/nope/status')
      .set('authorization', viewerAuth)
      .expect(404);
  });
});

describe('POST /api/gates/:id/command-level', () => {
  test('viewer is forbidden (403) and nothing is written', async () => {
    const ctx = setup();
    await request(ctx.app)
      .post('/api/gates/waste-way/command-level')
      .set('authorization', viewerAuth)
      .send({ targetValue: 2, confirmed: true })
      .expect(403);
    expect(ctx.writes).toEqual([]);
  });

  test('operator command is accepted (202), writes occur, and an audit entry is recorded', async () => {
    const ctx = setup();
    const res = await request(ctx.app)
      .post('/api/gates/waste-way/command-level')
      .set('authorization', operatorAuth)
      .send({ targetValue: 3, confirmed: true })
      .expect(202);
    expect(res.body.status).toBe('accepted');
    expect(ctx.writes).toEqual([
      { kind: 'hr', address: 108, value: 3 },
      { kind: 'coil', address: 17, value: true },
    ]);
    expect(ctx.audit.entries).toMatchObject([{ result: 'ok', requestedTarget: 3 }]);
  });

  test('out-of-range target is rejected 400 (invalid_target)', async () => {
    const res = await request(setup().app)
      .post('/api/gates/waste-way/command-level')
      .set('authorization', operatorAuth)
      .send({ targetValue: 9, confirmed: true })
      .expect(400);
    expect(res.body.reason).toBe('invalid_target');
  });

  test('unconfirmed command is rejected 400 (not_confirmed)', async () => {
    const res = await request(setup().app)
      .post('/api/gates/waste-way/command-level')
      .set('authorization', operatorAuth)
      .send({ targetValue: 2, confirmed: false })
      .expect(400);
    expect(res.body.reason).toBe('not_confirmed');
  });

  test('malformed body is rejected 400 with validation details', async () => {
    const res = await request(setup().app)
      .post('/api/gates/waste-way/command-level')
      .set('authorization', operatorAuth)
      .send({ targetValue: 'two' })
      .expect(400);
    expect(res.body.error).toBe('invalid body');
  });
});

describe('POST /api/gates/:id/horn', () => {
  test('operator horn-on is accepted and writes coil 15', async () => {
    const ctx = setup();
    await request(ctx.app)
      .post('/api/gates/waste-way/horn')
      .set('authorization', operatorAuth)
      .send({ enabled: true, confirmed: true })
      .expect(202);
    expect(ctx.writes).toEqual([{ kind: 'coil', address: 15, value: true }]);
  });
});

describe('GET /metrics', () => {
  test('is unauthenticated and exposes the pre-registered series in Prometheus text', async () => {
    const res = await request(setup().app).get('/metrics').expect(200);
    expect(res.headers['content-type']).toContain('text/plain');
    expect(res.text).toContain('# TYPE machine_modbus_writes_total counter');
    expect(res.text).toContain('machine_modbus_writes_total{mode="operator"} 0');
    expect(res.text).toContain('command_intent_rejections_total{reason="schema_invalid"} 0');
  });
});

describe('command rate limiting', () => {
  test('a second command beyond the per-user limit is rejected 429', async () => {
    const ctx = setup({ windowMs: 60_000, max: 1 });
    const post = () =>
      request(ctx.app)
        .post('/api/gates/waste-way/command-level')
        .set('authorization', operatorAuth)
        .send({ targetValue: 2, confirmed: true });
    await post().expect(202);
    await post().expect(429);
  });
});
