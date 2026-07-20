import { sha256OfCanonicalJson } from './canonical-hash';
import type { CommandIntent } from './machine-boundary';

/**
 * PR 6.2 — the cross-service intent content hash:
 *
 *   sha256( JCS(command_intent) )        // NO domain prefix
 *
 * JCS = RFC 8785 canonical JSON via the `canonicalize` reference library. This
 * MUST byte-reproduce the Scheduler's `command_intent_content_hash`
 * (`sha256(canonicalize(intent.model_dump()))` in
 * `services/scheduler/src/core/command_intent.py`); a golden cross-language vector
 * pins it in `intent-content-hash.spec.ts`. It is the durable idempotency/replay
 * key stored in the receipt, and the `idempotency_conflict` discriminator.
 *
 * NB: shares the `sha256OfCanonicalJson` plumbing with `computeCapabilityHash` but,
 * deliberately, supplies NO domain prefix (the capability hash prepends one).
 */
export function intentContentHash(intent: CommandIntent): string {
  return sha256OfCanonicalJson(intent);
}
