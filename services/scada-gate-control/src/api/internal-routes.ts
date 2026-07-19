/**
 * PR 6.1a — internal, service-to-service capability surface.
 *
 *   GET /internal/v1/device-capabilities   (authenticated, read-only)
 *
 * Serves the content-hashed device-capability snapshot loaded at startup. NO
 * dispatcher, NO actuation, NO write path — the scheduler (6.2) re-fetches and
 * pins this snapshot before compiling intents. An empty snapshot means zero
 * machine-capable gates. Never fetched from the browser.
 *
 * This is a service-to-service surface (the scheduler carries an operator/service
 * token), so it requires Operator+ — a read-only Viewer/guest MUST NOT enumerate
 * which gates are machine-controllable.
 */
import { Router } from 'express';

import { requireAuth, requireRole } from './middleware';
import type { ApiDeps } from './routes';

export function buildInternalRouter(
  deps: Pick<ApiDeps, 'verifier' | 'deviceCapabilities'>,
): Router {
  const router = Router();
  const auth = requireAuth(deps.verifier);

  router.get('/v1/device-capabilities', auth, requireRole('operator'), (_req, res) => {
    res.set('Cache-Control', 'no-store');
    res.json(deps.deviceCapabilities);
  });

  return router;
}
