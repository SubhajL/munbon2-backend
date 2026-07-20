import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import type { Express } from 'express';
import jwt from 'jsonwebtoken';
import request from 'supertest';
import { describe, expect, it } from 'vitest';

import { InMemoryAuditRepository } from '../audit/memory-repository';
import { InMemoryCommandIntentReceiptRepository } from '../command-intents/memory-repository';
import type { CommandIntent, DeviceCapabilitySnapshot } from '../domain/machine-boundary';
import type { ApprovedLineageAnchor } from '../domain/approved-field-artifact';
import { CommandService } from '../services/command-service';
import { buildSnapshot, emptyState, recordPoll, type GateSnapshot } from '../state/store';
import type { GateActuator } from '../state/gate-controller';
import type { ModbusWrite } from '../domain/command';
import type { PointReads } from '../transport/types';
import { JwtTokenVerifier } from './auth';
import { SchedulerServiceTokenVerifier } from './service-auth';
import { buildServer } from './server';

const OP_SECRET = 'op-secret';
const OP_ISSUER = 'munbon-auth';
const OP_AUDIENCE = 'munbon-api';

const SVC_SECRET = 'svc-secret';
const SVC_ISSUER = 'munbon-scheduler';
const SVC_AUDIENCE = 'munbon-scada-machine-boundary';

const IN_WINDOW_MS = Date.parse('2026-07-20T03:00:00Z'); // within the fixture's not_before..deadline
const thresholds = { staleAfterMs: 10_000, offlineAfterMs: 20_000 };
const site = { gateId: 'waste-way', name: 'Waste Way' };
const endpoint = { host: '172.16.1.103', port: 502, unitId: 1 };

function fixture(rel: string): unknown {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'contracts', 'machine-boundary', 'v1', rel);
    if (existsSync(candidate)) return JSON.parse(readFileSync(candidate, 'utf-8'));
    dir = dirname(dir);
  }
  throw new Error(`fixture not found: ${rel}`);
}

const SHADOW = fixture('fixtures/valid/command-intent.shadow.valid.json') as CommandIntent;

// A snapshot whose one gate binding exactly matches the shadow fixture (accepted path).
const MATCHING_SNAPSHOT = {
  schema_version: 1,
  capability_release_id: 'cap-2026-07-19-a',
  capability_hash: 'a'.repeat(64),
  capabilities: {
    'M(0,0;1,0)': {
      device_id: 'scada-rtu-07',
      adapter_gate_id: 'ch3',
      targets: [{ target_position_m: 0.45, target_level: 3 }],
    },
  },
} as unknown as DeviceCapabilitySnapshot;

const EMPTY_SNAPSHOT = {
  schema_version: 1,
  capability_release_id: '__empty__',
  capability_hash: 'e'.repeat(64),
  capabilities: {},
} as unknown as DeviceCapabilitySnapshot;

const okSnapshot: GateSnapshot = buildSnapshot(
  recordPoll(emptyState(), {
    ok: true,
    atMs: 1_000,
    reads: { gateLevel: 2, doorSw: 1, horn: 0, gateCf: 0 } as PointReads,
  }),
  1_000,
  thresholds,
);

function serviceToken(overrides: jwt.SignOptions = {}, payload: object = {}): string {
  return jwt.sign({ sub: 'svc:scheduler', type: 'service', ...payload }, SVC_SECRET, {
    issuer: SVC_ISSUER,
    audience: SVC_AUDIENCE,
    expiresIn: '5m',
    ...overrides,
  });
}

function makeApp(
  opts: {
    snapshot?: DeviceCapabilitySnapshot;
    serviceConfigured?: boolean;
    approvedLineageAnchor?: ApprovedLineageAnchor | null;
    siteCanonicalGateId?: string | null;
  } = {},
) {
  const writes: ModbusWrite[] = [];
  const actuator: GateActuator = {
    snapshot: () => okSnapshot,
    executeWrites: async (planned: readonly ModbusWrite[]) => {
      writes.push(...planned);
      return { succeeded: planned, failed: null, snapshot: okSnapshot };
    },
  };
  const receipts = new InMemoryCommandIntentReceiptRepository();
  const commandService = new CommandService({
    actuator,
    audit: new InMemoryAuditRepository(),
    now: () => IN_WINDOW_MS,
    endpoint,
    site,
  });
  const app = buildServer({
    verifier: new JwtTokenVerifier({ secret: OP_SECRET, issuer: OP_ISSUER, audience: OP_AUDIENCE }),
    commandService,
    snapshot: () => okSnapshot,
    site,
    endpoint,
    rateLimit: { windowMs: 60_000, max: 100 },
    deviceCapabilities: opts.snapshot ?? MATCHING_SNAPSHOT,
    serviceVerifier:
      opts.serviceConfigured === false
        ? null
        : new SchedulerServiceTokenVerifier({
            secret: SVC_SECRET,
            issuer: SVC_ISSUER,
            audience: SVC_AUDIENCE,
            maxAge: '5m',
          }),
    receipts,
    clock: () => IN_WINDOW_MS,
    approvedLineageAnchor: opts.approvedLineageAnchor ?? null,
    siteCanonicalGateId: opts.siteCanonicalGateId ?? null,
  });
  return { app, writes, receipts };
}

const post = (app: Express, token: string | null, body: unknown) => {
  const req = request(app).post('/internal/v1/command-intents/validate');
  return token
    ? req.set('Authorization', `Bearer ${token}`).send(body as object)
    : req.send(body as object);
};

describe('POST /internal/v1/command-intents/validate', () => {
  it('accepts a valid shadow intent and returns a durable receipt (the done gate)', async () => {
    const { app, writes, receipts } = makeApp();
    const res = await post(app, serviceToken(), SHADOW).expect(200);
    expect(res.body.status).toBe('validation_accepted');
    expect(res.body.reason_code).toBeNull();
    expect(res.body.intent_content_hash).toBe(
      '3ef5a28c4937e5b4d541b214a8b89c8b8a6a088807371634c87d5142f2804216',
    );
    // Durable: the receipt is persisted under the intent's idempotency_key.
    expect(await receipts.getByIdempotencyKey(SHADOW.idempotency_key)).not.toBeNull();
    // No-write boundary: the accepted validation issued ZERO Modbus writes.
    expect(writes).toEqual([]);
  });

  it('test_validate_route_cannot_reach_actuator: no request kind ever writes Modbus', async () => {
    const { app, writes } = makeApp();
    await post(app, serviceToken(), SHADOW).expect(200); // accepted
    await post(app, serviceToken(), {
      ...SHADOW,
      idempotency_key: 'other-key-freshness',
      capability_hash: 'b'.repeat(64),
    }).expect(200); // rejected (freshness), distinct key
    await post(app, serviceToken(), SHADOW).expect(200); // replay (same key + body)
    await post(app, serviceToken(), { ...SHADOW, target_level: 4 }).expect(409); // conflict (same key, diff body)
    await post(app, serviceToken(), { nonsense: true }).expect(422); // schema_invalid
    await post(app, null, SHADOW).expect(401); // no token
    expect(writes).toEqual([]);
  });

  it('test_duplicate_intent_returns_prior_receipt: replay returns the identical stored receipt', async () => {
    const { app, receipts } = makeApp();
    const first = await post(app, serviceToken(), SHADOW).expect(200);
    const second = await post(app, serviceToken(), SHADOW).expect(200);
    expect(second.body).toEqual(first.body);
    expect(second.body.receipt_id).toBe(first.body.receipt_id);
    // Exactly one durable row for the key.
    const stored = await receipts.getByIdempotencyKey(SHADOW.idempotency_key);
    expect(JSON.parse(stored!.receipt_document)).toEqual(first.body);
  });

  it('test_same_key_different_payload_rejects_conflict: 409 and the stored row is untouched', async () => {
    const { app, receipts } = makeApp();
    const accepted = await post(app, serviceToken(), SHADOW).expect(200);
    const conflict = await post(app, serviceToken(), { ...SHADOW, target_level: 4 }).expect(409);
    expect(conflict.body.status).toBe('validation_rejected');
    expect(conflict.body.reason_code).toBe('idempotency_conflict');
    // The winning row still resolves to the ORIGINAL accepted receipt (never mutated).
    const stored = await receipts.getByIdempotencyKey(SHADOW.idempotency_key);
    expect(JSON.parse(stored!.receipt_document)).toEqual(accepted.body);
  });

  it('test_wrong_audience_or_expired_service_token_rejects: strict service auth', async () => {
    const { app } = makeApp();
    await post(app, serviceToken({ audience: 'munbon-api' }), SHADOW).expect(401);
    await post(app, serviceToken({ expiresIn: '-1m' }), SHADOW).expect(401);
    await post(
      app,
      jwt.sign({ sub: 'u', type: 'access' }, OP_SECRET, {
        issuer: OP_ISSUER,
        audience: OP_AUDIENCE,
        expiresIn: '5m',
      }),
      SHADOW,
    ).expect(401);
  });

  it('persists a merit rejection and replays it (freshness_failed vs the dark snapshot)', async () => {
    const { app, receipts } = makeApp({ snapshot: EMPTY_SNAPSHOT });
    const first = await post(app, serviceToken(), SHADOW).expect(200);
    expect(first.body.status).toBe('validation_rejected');
    expect(first.body.reason_code).toBe('freshness_failed');
    const replay = await post(app, serviceToken(), SHADOW).expect(200);
    expect(replay.body).toEqual(first.body);
    expect(await receipts.getByIdempotencyKey(SHADOW.idempotency_key)).not.toBeNull();
  });

  it('PR 6.1b: a configured lineage anchor rejects an unapproved intent as lineage_mismatch (no writes)', async () => {
    const { app, writes, receipts } = makeApp({
      approvedLineageAnchor: {
        model_release_id: 'a-different-approved-release',
        model_release_content_hash: 'c'.repeat(64),
        engine_descriptor_content_hash: 'd'.repeat(64),
      },
    });
    const res = await post(app, serviceToken(), SHADOW).expect(200);
    expect(res.body.status).toBe('validation_rejected');
    expect(res.body.reason_code).toBe('lineage_mismatch');
    expect(await receipts.getByIdempotencyKey(SHADOW.idempotency_key)).not.toBeNull();
    expect(writes).toEqual([]);
  });

  it('PR 6.1b: a matching lineage anchor still accepts the approved intent', async () => {
    const { app } = makeApp({
      approvedLineageAnchor: {
        model_release_id: 'engineering-prior-v3-v1',
        model_release_content_hash: '5'.repeat(64),
        engine_descriptor_content_hash: '7'.repeat(64),
      },
    });
    const res = await post(app, serviceToken(), SHADOW).expect(200);
    expect(res.body.status).toBe('validation_accepted');
    expect(res.body.reason_code).toBeNull();
  });

  it('rejects a schema-invalid intent with 422 and persists NO receipt', async () => {
    const { app, receipts } = makeApp();
    const res = await post(app, serviceToken(), { ...SHADOW, event_kind: 'nope' }).expect(422);
    expect(res.body.reason_code).toBe('schema_invalid');
    expect(await receipts.getByIdempotencyKey(SHADOW.idempotency_key)).toBeNull();
  });

  it('returns 503 when service auth is not configured (dark endpoint)', async () => {
    const { app } = makeApp({ serviceConfigured: false });
    await post(app, serviceToken(), SHADOW).expect(503);
  });

  it('returns 401 when the bearer token is missing', async () => {
    const { app } = makeApp();
    await post(app, null, SHADOW).expect(401);
  });

  it('returns 400 for a malformed JSON body (authenticated)', async () => {
    const { app } = makeApp();
    await request(app)
      .post('/internal/v1/command-intents/validate')
      .set('Authorization', `Bearer ${serviceToken()}`)
      .set('Content-Type', 'application/json')
      .send('{ not json')
      .expect(400);
  });

  it('auth gates before body parsing: malformed JSON with NO token is 401, not 400', async () => {
    const { app } = makeApp();
    await request(app)
      .post('/internal/v1/command-intents/validate')
      .set('Content-Type', 'application/json')
      .send('{ not json')
      .expect(401);
  });

  it('auth gates before body parsing: malformed JSON against a dark endpoint is 503, not 400', async () => {
    const { app } = makeApp({ serviceConfigured: false });
    await request(app)
      .post('/internal/v1/command-intents/validate')
      .set('Authorization', `Bearer ${serviceToken()}`)
      .set('Content-Type', 'application/json')
      .send('{ not json')
      .expect(503);
  });
});

describe('GET /internal/v1/gate-readback (PR 6.3b)', () => {
  const getReadback = (app: Express, token: string | null) => {
    const req = request(app).get('/internal/v1/gate-readback');
    return token ? req.set('Authorization', `Bearer ${token}`) : req;
  };

  it('is DARK (503) when the service secret is unset', async () => {
    const { app } = makeApp({ serviceConfigured: false });
    await getReadback(app, serviceToken()).expect(503);
  });

  it('rejects a missing token (401) and an operator token (401) — it is service-authed', async () => {
    const { app } = makeApp();
    await getReadback(app, null).expect(401);
    const operatorToken = jwt.sign(
      { sub: 'op', type: 'access', roles: ['zone_manager'] },
      OP_SECRET,
      {
        issuer: OP_ISSUER,
        audience: OP_AUDIENCE,
        expiresIn: '5m',
      },
    );
    await getReadback(app, operatorToken).expect(401);
  });

  it('serves an unavailable machine gate when no site canonical gate is configured (no-store)', async () => {
    const { app } = makeApp(); // MATCHING_SNAPSHOT has gate M(0,0;1,0); siteCanonicalGateId null
    const res = await getReadback(app, serviceToken()).expect(200);
    expect(res.headers['cache-control']).toBe('no-store');
    expect(res.body.gates['M(0,0;1,0)'].observed_level).toBeNull();
    expect(res.body.gates['M(0,0;1,0)'].quality).toBe('unavailable');
  });

  it('attaches the live poll level when the gate is the configured site gate', async () => {
    const { app } = makeApp({ siteCanonicalGateId: 'M(0,0;1,0)' });
    const res = await getReadback(app, serviceToken()).expect(200);
    // okSnapshot polled gateLevel raw = 2.
    expect(res.body.gates['M(0,0;1,0)'].observed_level).toBe(2);
    expect(res.body.gates['M(0,0;1,0)'].quality).toBe('ok');
  });
});
