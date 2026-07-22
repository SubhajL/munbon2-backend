import { execFileSync } from 'child_process';

export function runReadOnlyPsql(query: string): string {
  const connection = process.env.POSTGRES_URL;
  if (!connection) throw new Error('POSTGRES_URL is required for the read-only database probe');
  let parsed: URL;
  try {
    parsed = new URL(connection);
  } catch {
    throw new Error('POSTGRES_URL is invalid');
  }
  if (!['postgres:', 'postgresql:'].includes(parsed.protocol) || !parsed.hostname) {
    throw new Error('POSTGRES_URL is invalid');
  }
  const inheritedEnv = { ...process.env };
  delete inheritedEnv.POSTGRES_URL;
  try {
    return execFileSync('psql', ['--no-psqlrc', '-X', '-At', '-F', '\t', '-c', query], {
      encoding: 'utf8',
      timeout: 5_000,
      maxBuffer: 64 * 1_024,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...inheritedEnv,
        PGHOST: parsed.hostname,
        PGPORT: parsed.port || '5432',
        PGUSER: decodeURIComponent(parsed.username),
        PGPASSWORD: decodeURIComponent(parsed.password),
        PGDATABASE: decodeURIComponent(parsed.pathname.replace(/^\//u, '')),
        PGOPTIONS: '-c default_transaction_read_only=on -c statement_timeout=2000',
      },
    });
  } catch {
    throw new Error('read-only database probe failed');
  }
}
