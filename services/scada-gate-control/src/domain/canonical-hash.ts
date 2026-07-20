import { createHash } from 'crypto';

import canonicalize from 'canonicalize';

/**
 * The single canonical-JSON content-hash primitive for the machine boundary:
 *
 *   sha256( prefix || JCS(value) )
 *
 * JCS = RFC 8785 canonical JSON via the `canonicalize` reference library. The
 * OPTIONAL domain `prefix` is the only intended variation between callers — the
 * device-capability snapshot hash prepends `munbon:device-capability-snapshot:v1\n`,
 * the command-intent content hash prepends nothing. Consolidated here so the two
 * hashes can never fork in how they serialize/encode (root CLAUDE.md: "consolidate,
 * don't fork").
 */
export function sha256OfCanonicalJson(value: unknown, prefix = ''): string {
  const jcs = canonicalize(value);
  if (jcs === undefined) {
    throw new Error('value is not JCS-serialisable');
  }
  return createHash('sha256')
    .update(Buffer.from(prefix + jcs, 'utf-8'))
    .digest('hex');
}
