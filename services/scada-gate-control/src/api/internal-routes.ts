/**
 * Internal, service-to-service surface.
 *
 *   GET  /internal/v1/device-capabilities        (PR 6.1a — operator-token, read-only)
 *   POST /internal/v1/command-intents/validate    (PR 6.2  — scheduler service-token)
 *
 * The validate endpoint is VALIDATION-ONLY: it holds no CommandService, GateController,
 * or transport — there is no code path from here to a Modbus write, by construction. It
 * returns a durable, idempotent 6.0 ValidationReceipt. Never reached from the browser.
 */
import { randomUUID } from 'crypto';

import express, { Router, type Request, type Response } from 'express';

import {
  buildValidationReceipt,
  compileCommandIntentValidator,
  formatUtcInstant,
  parseUtcInstant,
  validateCommandIntent,
} from '../domain/command-intent-validation';
import { intentContentHash } from '../domain/intent-content-hash';
import { projectGateReadback } from '../domain/gate-readback';
import type { CommandIntent } from '../domain/machine-boundary';
import type { ExecuteCommandIntentRequest } from '../command-executions/types';
import type { ValidationReceiptRecord } from '../command-intents/types';
import { logger } from '../utils/logger';
import type { ExecutionOutcomeRecorder, RejectionRecorder } from '../metrics/registry';
import { requireServiceAuth, requireServiceScope } from './service-auth';
import { requireAuth, requireRole } from './middleware';
import type { ApiDeps } from './routes';

// The machine boundary gets ONLY the rejection recorder, never the full ScadaMetrics — so it
// is type-impossible for the no-actuator validate/readback router to record a Modbus write
// (which would emit a phantom shadow-write tripwire hit). Mirrors the no-CommandService rule.
type InternalDeps = Pick<
  ApiDeps,
  | 'verifier'
  | 'deviceCapabilities'
  | 'serviceVerifier'
  | 'receipts'
  | 'clock'
  | 'approvedLineageAnchor'
  | 'snapshot'
  | 'siteCanonicalGateId'
  | 'machineExecutionService'
> & { readonly metrics: RejectionRecorder & ExecutionOutcomeRecorder };

/** Return a stored receipt (idempotent replay) or a 409 conflict, without persisting. */
function respondFromExisting(
  res: Response,
  stored: ValidationReceiptRecord,
  intent: CommandIntent,
  contentHash: string,
  nowMs: number,
): void {
  if (stored.intent_content_hash === contentHash) {
    // Same key, same intent -> idempotent replay of the durable receipt, verbatim.
    res.status(200).json(JSON.parse(stored.receipt_document));
    return;
  }
  // Same key, DIFFERENT intent -> conflict. Ephemeral rejected receipt; the stored
  // winning row is never mutated (a replay cannot rewrite an intent).
  const receipt = buildValidationReceipt({
    intent,
    verdict: { status: 'validation_rejected', reason_code: 'idempotency_conflict' },
    receiptId: randomUUID(),
    validatedAt: formatUtcInstant(nowMs),
    contentHash,
  });
  res.status(409).json(receipt);
}

export function buildInternalRouter(deps: InternalDeps): Router {
  const router = Router();
  const auth = requireAuth(deps.verifier);
  // Compile the Ajv validator once at router-build (startup) time — fail fast on a bad
  // schema, and don't recompile-check per request. Mirrors routes.ts hoisting its schemas.
  const validateIntent = compileCommandIntentValidator();

  router.get('/v1/device-capabilities', auth, requireRole('operator'), (_req, res) => {
    res.set('Cache-Control', 'no-store');
    res.json(deps.deviceCapabilities);
  });

  // PR 6.3b — service-authed machine-boundary readback (dark 503 when the service secret is
  // unset). The scheduler's shadow reconciler reads this with its SERVICE token — never operator
  // creds. Read-only: it holds no actuator/transport, so there is no write path from here.
  router.get(
    '/v1/gate-readback',
    requireServiceAuth(deps.serviceVerifier),
    requireServiceScope('gate_readback.read'),
    (_req, res) => {
      res.set('Cache-Control', 'no-store');
      res.json(
        projectGateReadback(
          deps.deviceCapabilities,
          deps.snapshot(),
          deps.siteCanonicalGateId,
          new Date(deps.clock()).toISOString(),
        ),
      );
    },
  );

  router.post(
    '/v1/command-intents/validate',
    // Auth gates BEFORE any body parsing: an unauthenticated or dark-endpoint request is
    // rejected (401/503) without parsing work, and a bad token + malformed body yields
    // 401/503 (the security answer) rather than 400 from the parser.
    requireServiceAuth(deps.serviceVerifier),
    requireServiceScope('command_intents.validate'),
    express.json({ limit: '8kb' }), // a command intent with max-length ids exceeds the /api 2kb cap
    async (req: Request, res: Response, next) => {
      try {
        if (!validateIntent(req.body)) {
          // A malformed intent cannot mint a trustworthy keyable receipt: 422, no receipt.
          // schema_invalid is the ONLY rejection reason SCADA counts: its 422 body is a plain
          // error (no receipt) that the scheduler persists nowhere, so it is invisible to the
          // scheduler's 0010-derived metric. Every other reason DOES leave a durable receipt
          // the scheduler counts — the merit rejections via a 200 receipt, and even
          // idempotency_conflict via the 409 body, which is itself a ValidationReceipt the
          // scheduler dispatcher persists into control_command_validation_receipts (PR 6.3a).
          deps.metrics.recordSchemaInvalidRejection();
          res.status(422).json({
            error: 'command intent failed schema validation',
            reason_code: 'schema_invalid',
            details: validateIntent.errors,
          });
          return;
        }
        const intent = req.body as CommandIntent;
        const contentHash = intentContentHash(intent);

        let existing: ValidationReceiptRecord | null;
        try {
          existing = await deps.receipts.getByIdempotencyKey(intent.idempotency_key);
        } catch (error) {
          logger.error(
            { err: error instanceof Error ? error.message : String(error) },
            'receipt store lookup failed',
          );
          res.status(503).json({ error: 'receipt store unavailable' });
          return;
        }
        if (existing) {
          respondFromExisting(res, existing, intent, contentHash, deps.clock());
          return;
        }

        const nowMs = deps.clock();
        const verdict = validateCommandIntent(
          intent,
          deps.deviceCapabilities,
          nowMs,
          deps.approvedLineageAnchor,
        );
        const receipt = buildValidationReceipt({
          intent,
          verdict,
          receiptId: randomUUID(),
          validatedAt: formatUtcInstant(nowMs),
          contentHash,
        });
        const record: ValidationReceiptRecord = {
          idempotency_key: intent.idempotency_key,
          intent_id: intent.intent_id,
          correlation_id: intent.correlation_id,
          request_id: intent.request_id,
          intent_content_hash: contentHash,
          capability_hash: intent.capability_hash,
          receipt_id: receipt.receipt_id,
          status: receipt.status,
          reason_code: receipt.reason_code,
          validated_at: receipt.validated_at,
          receipt_document: JSON.stringify(receipt),
        };

        let outcome;
        try {
          outcome = await deps.receipts.insertIfAbsent(record);
        } catch (error) {
          logger.error(
            { err: error instanceof Error ? error.message : String(error) },
            'receipt store insert failed',
          );
          res.status(503).json({ error: 'receipt store unavailable' });
          return;
        }
        if (outcome.inserted) {
          // A well-formed intent that is rejected on its merits is still a SUCCESSFUL
          // validation -> 200 with the receipt; the caller reads receipt.status.
          res.status(200).json(receipt);
          return;
        }
        // Lost the insert race: the durable winner decides replay vs conflict.
        respondFromExisting(res, outcome.stored, intent, contentHash, deps.clock());
      } catch (error) {
        next(error);
      }
    },
  );

  router.post(
    '/v1/command-intents/execute',
    requireServiceAuth(deps.serviceVerifier),
    express.json({ limit: '10kb' }),
    async (req: Request, res: Response) => {
      const body = req.body as Partial<ExecuteCommandIntentRequest> | null;
      if (
        body === null ||
        typeof body !== 'object' ||
        !validateIntent(body.intent) ||
        typeof body.grant_id !== 'string' ||
        typeof body.authority_not_after !== 'string' ||
        typeof body.original_intent_content_hash !== 'string' ||
        typeof body.execution_intent_content_hash !== 'string' ||
        (body.purpose !== 'operator_approved' && body.purpose !== 'fail_safe_close')
      ) {
        res.status(422).json({ error: 'execution request failed schema validation' });
        return;
      }
      const executionRequest = body as ExecuteCommandIntentRequest;
      const principal = req.serviceAuth;
      const authorityNotAfter = parseUtcInstant(executionRequest.authority_not_after);
      const requiredScope =
        executionRequest.purpose === 'operator_approved'
          ? 'command_intents.execute'
          : 'command_intents.fail_safe_close';
      if (
        !principal ||
        principal.scope !== requiredScope ||
        !principal.jti ||
        typeof principal.expiresAtMs !== 'number' ||
        authorityNotAfter === null ||
        principal.expiresAtMs > authorityNotAfter ||
        principal.grantId !== executionRequest.grant_id ||
        principal.authorityNotAfter !== executionRequest.authority_not_after ||
        principal.intentId !== executionRequest.intent.intent_id ||
        principal.originalIntentContentHash !== executionRequest.original_intent_content_hash ||
        principal.executionIntentContentHash !== executionRequest.execution_intent_content_hash ||
        principal.purpose !== executionRequest.purpose
      ) {
        res.status(403).json({ error: 'service token is not bound to this execution request' });
        return;
      }
      if (!deps.machineExecutionService) {
        res.status(503).json({ error: 'machine execution is not configured' });
        return;
      }
      try {
        const receipt = await deps.machineExecutionService.executeCommandIntent(
          executionRequest,
          principal.expiresAtMs,
        );
        deps.metrics.recordExecutionOutcome(receipt.status, receipt.purpose);
        const status =
          receipt.reason_code === 'idempotency_conflict'
            ? 409
            : receipt.status === 'execution_rejected'
              ? 422
              : 200;
        res.status(status).json(receipt);
      } catch (error) {
        logger.error(
          { err: error instanceof Error ? error.message : String(error) },
          'machine execution failed closed',
        );
        res.status(503).json({ error: 'machine execution unavailable' });
      }
    },
  );

  return router;
}
