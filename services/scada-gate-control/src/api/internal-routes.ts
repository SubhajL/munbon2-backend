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
  validateCommandIntent,
} from '../domain/command-intent-validation';
import { intentContentHash } from '../domain/intent-content-hash';
import type { CommandIntent } from '../domain/machine-boundary';
import type { ValidationReceiptRecord } from '../command-intents/types';
import { logger } from '../utils/logger';
import { requireServiceAuth } from './service-auth';
import { requireAuth, requireRole } from './middleware';
import type { ApiDeps } from './routes';

type InternalDeps = Pick<
  ApiDeps,
  'verifier' | 'deviceCapabilities' | 'serviceVerifier' | 'receipts' | 'clock'
>;

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

  router.post(
    '/v1/command-intents/validate',
    // Auth gates BEFORE any body parsing: an unauthenticated or dark-endpoint request is
    // rejected (401/503) without parsing work, and a bad token + malformed body yields
    // 401/503 (the security answer) rather than 400 from the parser.
    requireServiceAuth(deps.serviceVerifier),
    express.json({ limit: '8kb' }), // a command intent with max-length ids exceeds the /api 2kb cap
    async (req: Request, res: Response, next) => {
      try {
        if (!validateIntent(req.body)) {
          // A malformed intent cannot mint a trustworthy keyable receipt: 422, no receipt.
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
        const verdict = validateCommandIntent(intent, deps.deviceCapabilities, nowMs);
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

  return router;
}
