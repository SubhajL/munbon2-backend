import express from 'express';
import jwt from 'jsonwebtoken';
import request from 'supertest';
import { describe, expect, it } from 'vitest';

import { emptyDeviceCapabilitySnapshot } from '../domain/device-registry';
import type { DeviceCapabilitySnapshot } from '../domain/machine-boundary';
import { JwtTokenVerifier } from './auth';
import { buildInternalRouter } from './internal-routes';

const SECRET = 'test-secret';
const ISSUER = 'munbon-auth';
const AUDIENCE = 'munbon-api';
function sign(roles: string[]): string {
  return jwt.sign({ sub: 'u1', roles, type: 'access' }, SECRET, {
    issuer: ISSUER,
    audience: AUDIENCE,
    expiresIn: '5m',
  });
}
// `zone_manager` maps to operator; `guest` maps to viewer (see DEFAULT_ROLE_MAPPING).
const operatorToken = sign(['zone_manager']);
const viewerToken = sign(['guest']);

const POPULATED = {
  schema_version: 1,
  capability_release_id: 'cap-x',
  capability_hash: 'a'.repeat(64),
  capabilities: {
    'M(0,0;1,0)': {
      device_id: 'scada-rtu-07',
      adapter_gate_id: 'ch3',
      targets: [{ target_position_m: 0.45, target_level: 3 }],
    },
  },
} as unknown as DeviceCapabilitySnapshot;

function makeApp(deviceCapabilities: DeviceCapabilitySnapshot): express.Express {
  const app = express();
  app.use(
    '/internal',
    buildInternalRouter({
      verifier: new JwtTokenVerifier({ secret: SECRET, issuer: ISSUER, audience: AUDIENCE }),
      deviceCapabilities,
    }),
  );
  return app;
}

describe('GET /internal/v1/device-capabilities', () => {
  it('401 without a token', async () => {
    await request(makeApp(POPULATED)).get('/internal/v1/device-capabilities').expect(401);
  });

  it('403 for an authenticated viewer (service surface requires Operator+)', async () => {
    await request(makeApp(POPULATED))
      .get('/internal/v1/device-capabilities')
      .set('Authorization', `Bearer ${viewerToken}`)
      .expect(403);
  });

  it('serves the snapshot to an authenticated operator, no-store', async () => {
    const res = await request(makeApp(POPULATED))
      .get('/internal/v1/device-capabilities')
      .set('Authorization', `Bearer ${operatorToken}`)
      .expect(200);
    expect(res.body.capability_hash).toBe('a'.repeat(64));
    expect(res.body.capabilities['M(0,0;1,0)'].device_id).toBe('scada-rtu-07');
    expect(res.headers['cache-control']).toBe('no-store');
  });

  it('serves the empty dark default (zero machine-capable gates)', async () => {
    const res = await request(makeApp(emptyDeviceCapabilitySnapshot()))
      .get('/internal/v1/device-capabilities')
      .set('Authorization', `Bearer ${operatorToken}`)
      .expect(200);
    expect(res.body.capabilities).toEqual({});
    expect(res.body.capability_release_id).toBe('__empty__');
  });
});
