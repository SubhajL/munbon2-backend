/**
 * REST routes per the spec's API surface:
 *   GET  /api/sites
 *   GET  /api/gates/:id/status
 *   POST /api/gates/:id/command-level   { targetValue, confirmed }
 *   POST /api/gates/:id/horn            { enabled, confirmed }
 * All routes require authentication (Viewer can read); writes are additionally
 * gated by the command service's safety planner.
 */
import express, { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import type { CommandOutcome, CommandService } from '../services/command-service';
import type { GateSnapshot } from '../state/store';
import type { WriteDenyReason } from '../domain/write-safety';
import type { DeviceCapabilitySnapshot } from '../domain/machine-boundary';
import type { ApprovedLineageAnchor } from '../domain/approved-field-artifact';
import type { CommandIntentReceiptRepository } from '../command-intents/types';
import type { ScadaMetrics } from '../metrics/registry';
import type { TokenVerifier } from './auth';
import type { ServiceTokenVerifier } from './service-auth';
import { requireAuth } from './middleware';
import { commandRateLimit, SlidingWindowRateLimiter, type RateLimitConfig } from './rate-limit';

export type ApiDeps = {
  readonly verifier: TokenVerifier;
  readonly commandService: CommandService;
  readonly snapshot: () => GateSnapshot;
  readonly site: { readonly gateId: string; readonly name: string };
  readonly endpoint: { readonly host: string; readonly port: number; readonly unitId: number };
  readonly rateLimit: RateLimitConfig;
  // PR 6.1a — the content-hashed device-capability snapshot, loaded once at
  // startup and served read-only via the internal capability endpoint.
  readonly deviceCapabilities: DeviceCapabilitySnapshot;
  // PR 6.2 — the machine-boundary validate endpoint's deps. serviceVerifier is null
  // when SCHEDULER_SERVICE_JWT_SECRET is unset (the endpoint then fails closed 503).
  readonly serviceVerifier: ServiceTokenVerifier | null;
  readonly receipts: CommandIntentReceiptRepository;
  readonly clock: () => number;
  // PR 6.1b — the approved lineage anchor for the reserved `lineage_mismatch` check, or null
  // (dark) when SCADA_APPROVED_LINEAGE_ANCHOR_PATH is unset (then validation is 6.2-identical).
  readonly approvedLineageAnchor: ApprovedLineageAnchor | null;
  // PR 6.3b — the canonical_gate_id of the polled site gate for the readback projection, or null.
  readonly siteCanonicalGateId: string | null;
  // PR 6.4 — the per-build Prometheus registry served at GET /metrics and incremented at the
  // write chokepoint (writeMeter) and the validate route (schema_invalid rejections).
  readonly metrics: ScadaMetrics;
};

const commandLevelSchema = z.object({ targetValue: z.number(), confirmed: z.boolean() });
const hornSchema = z.object({ enabled: z.boolean(), confirmed: z.boolean() });

const DENY_STATUS: Record<WriteDenyReason, number> = {
  not_authenticated: 401,
  role_forbidden: 403,
  data_stale: 409,
  data_offline: 409,
  data_unavailable: 409,
  not_confirmed: 400,
  invalid_target: 400,
};

function outcomeStatus(outcome: CommandOutcome): number {
  if (outcome.status === 'accepted') return 202;
  if (outcome.status === 'error') return 502;
  return DENY_STATUS[outcome.reason];
}

export function buildRouter(deps: ApiDeps): Router {
  const router = Router();
  router.use(express.json({ limit: '2kb' })); // command bodies are tiny (scoped here, not global)
  const auth = requireAuth(deps.verifier);
  const limiter = new SlidingWindowRateLimiter(deps.rateLimit);
  const rateLimit = commandRateLimit(
    limiter,
    (req) => `${req.auth?.userId ?? 'anon'}:${req.params.id}`,
  );

  const ensureGate = (req: Request, res: Response): boolean => {
    if (req.params.id !== deps.site.gateId) {
      res.status(404).json({ error: 'unknown gate' });
      return false;
    }
    return true;
  };

  router.get('/sites', auth, (_req, res) => {
    const snapshot = deps.snapshot();
    res.json([
      {
        id: deps.site.gateId,
        name: deps.site.name,
        connection: snapshot.connection,
        markerColor: snapshot.markerColor,
        lastUpdated: snapshot.lastUpdated,
      },
    ]);
  });

  router.get('/gates/:id/status', auth, (req, res) => {
    if (!ensureGate(req, res)) return;
    res.json({
      id: deps.site.gateId,
      name: deps.site.name,
      endpoint: deps.endpoint,
      ...deps.snapshot(),
    });
  });

  router.post('/gates/:id/command-level', auth, rateLimit, async (req, res, next) => {
    if (!ensureGate(req, res)) return;
    const user = req.auth;
    if (!user) {
      res.status(401).json({ error: 'unauthenticated' });
      return;
    }
    const parsed = commandLevelSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'invalid body', details: parsed.error.issues });
      return;
    }
    try {
      const outcome = await deps.commandService.commandGateLevel(
        user,
        parsed.data.targetValue,
        parsed.data.confirmed,
      );
      res.status(outcomeStatus(outcome)).json(outcome);
    } catch (error) {
      next(error);
    }
  });

  router.post('/gates/:id/horn', auth, rateLimit, async (req, res, next) => {
    if (!ensureGate(req, res)) return;
    const user = req.auth;
    if (!user) {
      res.status(401).json({ error: 'unauthenticated' });
      return;
    }
    const parsed = hornSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'invalid body', details: parsed.error.issues });
      return;
    }
    try {
      const outcome = await deps.commandService.commandHorn(
        user,
        parsed.data.enabled,
        parsed.data.confirmed,
      );
      res.status(outcomeStatus(outcome)).json(outcome);
    } catch (error) {
      next(error);
    }
  });

  return router;
}
