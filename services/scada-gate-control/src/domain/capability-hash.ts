import { createHash } from 'crypto';

import canonicalize from 'canonicalize';

/**
 * The FROZEN (PR 6.0) device-capability-snapshot content hash:
 *
 *   sha256( "munbon:device-capability-snapshot:v1\n" || JCS(snapshot without capability_hash) )
 *
 * JCS = RFC 8785 canonical JSON (object keys sorted at every level, array order
 * preserved, ES6-shortest numbers) via the `canonicalize` reference library. A
 * future Python producer/verifier (4.3c/6.2) must reproduce these exact bytes;
 * `capability-hash.spec.ts` pins a golden cross-language vector.
 */
export const CAPABILITY_HASH_DOMAIN_PREFIX = 'munbon:device-capability-snapshot:v1\n';

export function canonicalizeSnapshot(snapshotWithoutHash: Record<string, unknown>): string {
  const jcs = canonicalize(snapshotWithoutHash);
  if (jcs === undefined) {
    throw new Error('device-capability snapshot is not JCS-serialisable');
  }
  return jcs;
}

export function computeCapabilityHash(snapshotWithoutHash: Record<string, unknown>): string {
  const canonical = canonicalizeSnapshot(snapshotWithoutHash);
  return createHash('sha256')
    .update(Buffer.from(CAPABILITY_HASH_DOMAIN_PREFIX + canonical, 'utf-8'))
    .digest('hex');
}
