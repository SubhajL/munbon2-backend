import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import express from 'express';
import jwt from 'jsonwebtoken';
import request from 'supertest';
import { describe, expect, it, vi } from 'vitest';

import { InMemoryCommandIntentReceiptRepository } from '../command-intents/memory-repository';
import type { ExecutionReceipt } from '../command-executions/types';
import { intentContentHash } from '../domain/intent-content-hash';
import type { CommandIntent, DeviceCapabilitySnapshot } from '../domain/machine-boundary';
import { createScadaMetrics } from '../metrics/registry';
import { buildSnapshot, emptyState } from '../state/store';
import { buildInternalRouter } from './internal-routes';
import { SchedulerServiceTokenVerifier } from './service-auth';

const SECRET = 'scheduler-service-secret-value';
const ISSUER = 'munbon-scheduler';
const AUDIENCE = 'munbon-scada-machine-boundary';

function fixture(rel: string): unknown {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'contracts', 'machine-boundary', 'v1', rel);
    if (existsSync(candidate)) return JSON.parse(readFileSync(candidate, 'utf-8'));
    dir = dirname(dir);
  }
  throw new Error(`fixture not found: ${rel}`);
}

const original = fixture('fixtures/valid/command-intent.shadow.valid.json') as CommandIntent;
const promoted = { ...original, mode: 'operator_approved' } as CommandIntent;
const grantId = '77777777-7777-4777-8777-777777777777';
const authorityNotAfter = new Date(Date.now() + 300_000).toISOString();
const body = {
  intent: promoted,
  grant_id: grantId,
  authority_not_after: authorityNotAfter,
  original_intent_content_hash: intentContentHash(original),
  execution_intent_content_hash: intentContentHash(promoted),
  purpose: 'operator_approved' as const,
};
const receipt: ExecutionReceipt = {
  schema_version: 1,
  receipt_id: '11111111-1111-1111-1111-111111111111',
  intent_id: promoted.intent_id,
  idempotency_key: promoted.idempotency_key,
  grant_id: grantId,
  authority_not_after: authorityNotAfter,
  original_intent_content_hash: body.original_intent_content_hash,
  execution_intent_content_hash: body.execution_intent_content_hash,
  capability_hash: promoted.capability_hash,
  purpose: 'operator_approved',
  status: 'execution_succeeded',
  reason_code: null,
  target_level: promoted.target_level,
  observed_level: promoted.target_level,
  readback_quality: 'ok',
  writes: [],
  executed_at: '2026-07-20T03:00:00.000Z',
};

function token(scope = 'command_intents.execute', overrides: Record<string, unknown> = {}) {
  return jwt.sign(
    {
      sub: 'svc:scheduler',
      type: 'service',
      scope,
      jti: 'execute-1',
      grant_id: grantId,
      authority_not_after: authorityNotAfter,
      intent_id: promoted.intent_id,
      original_intent_content_hash: body.original_intent_content_hash,
      execution_intent_content_hash: body.execution_intent_content_hash,
      purpose: body.purpose,
      ...overrides,
    },
    SECRET,
    { issuer: ISSUER, audience: AUDIENCE, expiresIn: '4m' },
  );
}

function app(machineConfigured = true) {
  const executeCommandIntent = vi.fn().mockResolvedValue(receipt);
  const metrics = createScadaMetrics();
  const router = buildInternalRouter({
    verifier: { verify: () => ({ userId: 'operator', roles: ['operator'] }) },
    deviceCapabilities: {
      schema_version: 1,
      capability_release_id: promoted.capability_release_id,
      capability_hash: promoted.capability_hash,
      capabilities: {},
    } as DeviceCapabilitySnapshot,
    serviceVerifier: new SchedulerServiceTokenVerifier({
      secret: SECRET,
      issuer: ISSUER,
      audience: AUDIENCE,
      maxAge: '5m',
    }),
    receipts: new InMemoryCommandIntentReceiptRepository(),
    clock: () => Date.parse('2026-07-20T03:00:00Z'),
    approvedLineageAnchor: null,
    snapshot: () =>
      buildSnapshot(emptyState(), Date.parse('2026-07-20T03:00:00Z'), {
        staleAfterMs: 10_000,
        offlineAfterMs: 20_000,
      }),
    siteCanonicalGateId: null,
    metrics,
    ...(machineConfigured ? { machineExecutionService: { executeCommandIntent } } : {}),
  });
  const server = express();
  server.use('/internal', router);
  return { server, executeCommandIntent, metrics };
}

describe('POST /internal/v1/command-intents/execute', () => {
  it('cross-binds the execute token to the intent and both hashes', async () => {
    const { server, executeCommandIntent, metrics } = app();
    const response = await request(server)
      .post('/internal/v1/command-intents/execute')
      .set('Authorization', `Bearer ${token()}`)
      .send(body)
      .expect(200);
    expect(response.body).toEqual(receipt);
    expect(executeCommandIntent).toHaveBeenCalledWith(body, expect.any(Number));
    expect(await metrics.render()).toContain(
      'machine_execution_outcomes_total{purpose="operator_approved",status="execution_succeeded"} 1',
    );
  });

  it('does not let a validation-scoped token cross into execute', async () => {
    const { server, executeCommandIntent } = app();
    await request(server)
      .post('/internal/v1/command-intents/execute')
      .set('Authorization', `Bearer ${token('command_intents.validate')}`)
      .send(body)
      .expect(403);
    expect(executeCommandIntent).not.toHaveBeenCalled();
  });

  it('rejects a token whose promoted hash does not bind the request', async () => {
    const { server, executeCommandIntent } = app();
    await request(server)
      .post('/internal/v1/command-intents/execute')
      .set(
        'Authorization',
        `Bearer ${token('command_intents.execute', { execution_intent_content_hash: 'f'.repeat(64) })}`,
      )
      .send(body)
      .expect(403);
    expect(executeCommandIntent).not.toHaveBeenCalled();
  });

  it('rejects a token whose grant or authority deadline does not bind the request', async () => {
    const { server, executeCommandIntent } = app();
    await request(server)
      .post('/internal/v1/command-intents/execute')
      .set(
        'Authorization',
        `Bearer ${token('command_intents.execute', { grant_id: '88888888-8888-4888-8888-888888888888' })}`,
      )
      .send(body)
      .expect(403);
    expect(executeCommandIntent).not.toHaveBeenCalled();
  });

  it('keeps the route dark when no machine execution service is wired', async () => {
    const { server } = app(false);
    await request(server)
      .post('/internal/v1/command-intents/execute')
      .set('Authorization', `Bearer ${token()}`)
      .send(body)
      .expect(503);
  });
});
