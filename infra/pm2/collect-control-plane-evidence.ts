import { execFileSync } from 'child_process';
import { createHash } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { readBoundedResponse } from './bounded-http';
import { buildSafeEvidence } from './safe-evidence';
import { runReadOnlyPsql } from './postgres-evidence';
import { assessPm2Processes } from './pm2-evidence';
import type { DeploymentRole } from './deployment-preflight';

const REPO_ROOT = path.resolve(
  __dirname,
  path.basename(__dirname) === 'dist' ? '../../..' : '../..',
);
const MAX_HTTP_BYTES = 256 * 1024;
const MAX_ARTIFACT_BYTES = 2 * 1024 * 1024;

function values(name: string): string[] {
  return process.argv.flatMap((value, index) =>
    value === `--${name}` && process.argv[index + 1] ? [process.argv[index + 1]] : [],
  );
}

function value(name: string): string | undefined {
  return values(name)[0];
}

function gitHead(): string {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      timeout: 5_000,
      maxBuffer: 1_024,
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  } catch {
    throw new Error('release git probe failed');
  }
}

function pm2List(): unknown[] {
  try {
    const raw = execFileSync('pm2', ['jlist'], {
      encoding: 'utf8',
      timeout: 5_000,
      maxBuffer: 1024 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) throw new Error('invalid PM2 response');
    return parsed;
  } catch {
    throw new Error('PM2 status unavailable');
  }
}

async function fetchBounded(url: string, format: 'json' | 'text'): Promise<unknown> {
  const parsed = new URL(url);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) {
    throw new Error('probe URL is invalid');
  }
  const response = await fetch(parsed, { signal: AbortSignal.timeout(3_000) });
  const body = await readBoundedResponse(response, MAX_HTTP_BYTES);
  if (format === 'text') {
    if (!response.ok) throw new Error('probe returned a non-success response');
    return body;
  }
  const parsedBody = JSON.parse(body) as unknown;
  return typeof parsedBody === 'object' && parsedBody !== null && !Array.isArray(parsedBody)
    ? { ...parsedBody, http_status: response.status }
    : { http_status: response.status };
}

function schedulerDatabaseEvidence(): {
  migrations: { migration_id: string; checksum: string }[];
  counts: Record<string, number>;
} {
  const migrations = runReadOnlyPsql(
    'SELECT migration_id, checksum FROM scheduler.schema_migrations ORDER BY migration_id',
  )
    .trim()
    .split('\n')
    .filter(Boolean)
    .map(line => {
      const [migration_id, checksum, ...extra] = line.split('\t');
      if (!migration_id || !checksum || extra.length > 0) throw new Error('migration probe failed');
      return { migration_id, checksum };
    });
  const counts = runReadOnlyPsql(`SELECT
    (SELECT count(*) FROM scheduler.control_plan_runs),
    (SELECT count(*) FROM scheduler.control_authority_grants),
    (SELECT count(*) FROM scheduler.control_authority_grant_events),
    (SELECT count(*) FROM scheduler.control_authority_grant_events
       WHERE event_type IN ('granted', 'renewed')
         AND shadow_evidence_sha256 IS NOT NULL
         AND hold_drill_evidence_sha256 IS NOT NULL
         AND rollback_drill_evidence_sha256 IS NOT NULL)`)
    .trim()
    .split('\t')
    .map(item => Number(item));
  if (counts.length !== 4 || counts.some(item => !Number.isSafeInteger(item) || item < 0)) {
    throw new Error('count probe failed');
  }
  return {
    migrations,
    counts: {
      control_plan_runs: counts[0],
      authority_grants: counts[1],
      grant_events: counts[2],
      complete_drill_evidence_sets: counts[3],
    },
  };
}

function readBoundedJson(pathname: string): unknown {
  const stat = fs.statSync(pathname);
  if (!stat.isFile() || stat.size > MAX_ARTIFACT_BYTES) throw new Error('artifact is invalid');
  return JSON.parse(fs.readFileSync(pathname, 'utf8')) as unknown;
}

async function main(): Promise<void> {
  const role = value('role');
  const expectedCommit = value('expected-commit');
  if ((role !== 'central' && role !== 'field') || !expectedCommit) {
    throw new Error('--role central|field and --expected-commit are required');
  }
  const commit = gitHead();
  if (commit !== expectedCommit) throw new Error('release commit mismatch');
  const deploymentRole: DeploymentRole = role;
  const requiredUrlName = deploymentRole === 'central' ? 'scheduler-url' : 'scada-url';
  if (!value(requiredUrlName)) throw new Error(`--${requiredUrlName} is required for this role`);
  if (deploymentRole === 'central' && !value('release-file')) {
    throw new Error('--release-file is required for central release identity evidence');
  }
  const unavailable: Record<string, true> = {};
  let pm2: unknown[] = [];
  try {
    const expectedCwds: Record<string, string> =
      deploymentRole === 'central'
        ? {
            'flow-monitoring': path.join(REPO_ROOT, 'services', 'flow-monitoring'),
            scheduler: path.join(REPO_ROOT, 'services', 'scheduler'),
            'scheduler-control-dispatch': path.join(REPO_ROOT, 'services', 'scheduler'),
          }
        : { 'scada-gate-control': path.join(REPO_ROOT, 'services', 'scada-gate-control') };
    const assessment = assessPm2Processes(pm2List(), expectedCwds);
    pm2 = assessment.processes;
    for (const name of assessment.unavailable) unavailable[name] = true;
  } catch {
    unavailable.pm2 = true;
  }

  let migrations: { migration_id: string; checksum: string }[] = [];
  let counts: Record<string, number> = {};
  if (deploymentRole === 'central') {
    try {
      ({ migrations, counts } = schedulerDatabaseEvidence());
    } catch {
      unavailable.scheduler_database = true;
    }
  }

  const readiness: Record<string, unknown> = {};
  const metrics: Record<string, string> = {};
  const services = deploymentRole === 'central' ? (['scheduler'] as const) : (['scada'] as const);
  for (const service of services) {
    const baseUrl = value(`${service}-url`);
    if (!baseUrl) continue;
    try {
      readiness[service] = await fetchBounded(
        `${baseUrl.replace(/\/$/u, '')}/${service === 'scheduler' ? 'ready' : 'health'}`,
        'json',
      );
    } catch {
      unavailable[`${service}_readiness`] = true;
    }
    try {
      metrics[service] = (await fetchBounded(
        `${baseUrl.replace(/\/$/u, '')}/metrics`,
        'text',
      )) as string;
    } catch {
      unavailable[`${service}_metrics`] = true;
    }
  }

  const artifactHashes: Record<string, string> = {};
  for (const artifact of values('artifact')) {
    try {
      const stat = fs.statSync(artifact);
      if (!stat.isFile() || stat.size > MAX_ARTIFACT_BYTES) throw new Error('artifact is invalid');
      artifactHashes[artifact] = createHash('sha256')
        .update(fs.readFileSync(artifact))
        .digest('hex');
    } catch {
      unavailable.artifact_unavailable = true;
    }
  }
  let releaseIdentity: unknown = {};
  const releaseFile = value('release-file');
  if (releaseFile) {
    try {
      releaseIdentity = readBoundedJson(releaseFile);
    } catch {
      unavailable.release_identity = true;
    }
  }

  const evidence = buildSafeEvidence({
    collectedAt: new Date().toISOString(),
    commit,
    role: deploymentRole,
    migrations,
    pm2,
    readiness,
    metrics,
    artifactHashes,
    releaseIdentity,
    counts,
    unavailable,
  });
  process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`);
}

void main().catch(error => {
  process.stderr.write(
    `evidence collection failed: ${error instanceof Error ? error.message : 'unknown failure'}\n`,
  );
  process.exitCode = 1;
});
