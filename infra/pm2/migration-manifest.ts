import { createHash } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';

export function readTrackedMigrationManifest(repoRoot: string): Record<string, string> {
  const directory = path.join(repoRoot, 'services', 'scheduler', 'migrations');
  const ids = fs
    .readdirSync(directory)
    .filter(name => name.endsWith('.up.sql'))
    .map(name => name.slice(0, -'.up.sql'.length))
    .sort();
  return Object.fromEntries(
    ids.map(id => {
      const up = fs.readFileSync(path.join(directory, `${id}.up.sql`), 'utf8');
      const downPath = path.join(directory, `${id}.down.sql`);
      if (!fs.existsSync(downPath)) throw new Error('tracked migration pair is incomplete');
      const down = fs.readFileSync(downPath, 'utf8');
      return [id, createHash('sha256').update(`up\0${up}\0down\0${down}`).digest('hex')];
    }),
  );
}
