import { readFileSync } from 'fs';
import { join } from 'path';

import { describe, expect, it } from 'vitest';

// These packages are `import`ed by runtime code (device-registry + command-intent
// validation compile Ajv at startup/request time; canonicalize hashes intents). If any
// slips into devDependencies, a production `npm ci --omit=dev` deploy crashes at boot —
// exactly the latent 6.1a bug this guard prevents from recurring.
const RUNTIME_PACKAGES = ['ajv', 'ajv-formats', 'canonicalize'] as const;

describe('runtime dependency placement', () => {
  const pkg = JSON.parse(readFileSync(join(__dirname, '..', '..', 'package.json'), 'utf-8')) as {
    dependencies: Record<string, string>;
    devDependencies: Record<string, string>;
  };

  it.each(RUNTIME_PACKAGES)('lists %s under dependencies, not devDependencies', (name) => {
    expect(pkg.dependencies).toHaveProperty(name);
    expect(pkg.devDependencies).not.toHaveProperty(name);
  });
});
