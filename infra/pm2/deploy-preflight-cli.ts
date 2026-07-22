import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { getIrrigationProcesses } from './build-irrigation-config';
import { getScadaFieldProcesses } from './build-scada-field-config';
import { validateDeploymentPreflight, type DeploymentRole } from './deployment-preflight';
import { runReadOnlyPsql } from './postgres-evidence';
import { readTrackedMigrationManifest } from './migration-manifest';

const REPO_ROOT = path.resolve(
  __dirname,
  path.basename(__dirname) === 'dist' ? '../../..' : '../..',
);

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? undefined : process.argv[index + 1];
}

function readJson(pathname: string): unknown {
  const stat = fs.statSync(pathname);
  if (!stat.isFile() || stat.size > 1024 * 1024) throw new Error('evidence file is invalid');
  return JSON.parse(fs.readFileSync(pathname, 'utf8')) as unknown;
}

function appliedMigrations(pathname?: string): Record<string, string> {
  if (pathname) {
    const source = readJson(pathname);
    if (Array.isArray(source)) {
      return Object.fromEntries(
        source.map(row => {
          const value = row as { migration_id?: unknown; checksum?: unknown };
          if (typeof value.migration_id !== 'string' || typeof value.checksum !== 'string') {
            throw new Error('applied migration evidence is invalid');
          }
          return [value.migration_id, value.checksum];
        }),
      );
    }
    if (typeof source === 'object' && source !== null) return source as Record<string, string>;
    throw new Error('applied migration evidence is invalid');
  }
  const rows = runReadOnlyPsql(
    'SELECT migration_id, checksum FROM scheduler.schema_migrations ORDER BY migration_id',
  );
  return Object.fromEntries(
    rows
      .trim()
      .split('\n')
      .filter(Boolean)
      .map(line => {
        const columns = line.split('\t');
        if (columns.length !== 2) throw new Error('applied migration evidence is invalid');
        return columns;
      }),
  );
}

function git(...args: string[]): string {
  try {
    return execFileSync('git', args, {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      timeout: 5_000,
      maxBuffer: 64 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  } catch {
    throw new Error('release git probe failed');
  }
}

function main(): void {
  const role = argument('role');
  const expectedCommit = argument('expected-commit');
  if ((role !== 'central' && role !== 'field') || !expectedCommit) {
    throw new Error('--role central|field and --expected-commit are required');
  }
  const deploymentRole: DeploymentRole = role;
  const central = deploymentRole === 'central';
  const requiredPaths = central
    ? [
        'services/flow-monitoring/start.sh',
        'services/flow-monitoring/venv/bin/python',
        'services/flow-monitoring/venv/bin/uvicorn',
        'services/scheduler/start.sh',
        'services/scheduler/venv/bin/python',
        'services/scheduler/venv/bin/uvicorn',
        'services/scheduler/src/jobs/shadow_dispatch_once.py',
        'infra/pm2/dist/build-irrigation-config.js',
      ]
    : ['services/scada-gate-control/dist/index.js', 'infra/pm2/dist/build-scada-field-config.js'];
  const report = validateDeploymentPreflight({
    role: deploymentRole,
    expectedCommit,
    actualCommit: git('rev-parse', 'HEAD'),
    trackedTreeClean: git('status', '--porcelain', '--untracked-files=no') === '',
    trackedMigrations: central ? readTrackedMigrationManifest(REPO_ROOT) : {},
    appliedMigrations: central ? appliedMigrations(argument('applied-migrations')) : {},
    requiredFiles: Object.fromEntries(
      requiredPaths.map(relative => [
        relative,
        fs.statSync(path.join(REPO_ROOT, relative)).isFile(),
      ]),
    ),
    processes: central ? getIrrigationProcesses() : getScadaFieldProcesses(),
  });
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(
    `preflight failed: ${error instanceof Error ? error.message : 'unknown failure'}\n`,
  );
  process.exitCode = 1;
}
