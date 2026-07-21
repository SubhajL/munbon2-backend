import * as path from 'path';
import type { DeploymentRole } from './deployment-preflight';

type MigrationRow = {
  readonly migration_id: unknown;
  readonly checksum: unknown;
};

export type SafeEvidenceInput = {
  readonly collectedAt?: string;
  readonly commit: string;
  readonly role: DeploymentRole;
  readonly migrations: readonly MigrationRow[];
  readonly pm2: readonly unknown[];
  readonly readiness: Readonly<Record<string, unknown>>;
  readonly metrics: Readonly<Record<string, string>>;
  readonly artifactHashes: Readonly<Record<string, string>>;
  readonly releaseIdentity: unknown;
  readonly counts: unknown;
  readonly unavailable: Readonly<Record<string, unknown>>;
};

const SHA256 = /^[0-9a-f]{64}$/;
const COMMIT_SHA = /^[0-9a-f]{40}$/;
const SAFE_VALUE = /^[A-Za-z0-9_.:()/-]{1,128}$/;
const UTC_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/;
const SENSITIVE_MARKER = /secret|password|token|credential|authorization/i;
const MAX_METRIC_LINES = 200;
const COUNT_KEYS = [
  'control_plan_runs',
  'authority_grants',
  'grant_events',
  'complete_drill_evidence_sets',
] as const;
const RELEASE_STRING_PATHS = {
  model_release_id: [['model_release_id'], ['response_model', 'release_id']],
  model_release_content_hash: [['model_release_content_hash'], ['response_model', 'content_hash']],
  engine_descriptor_content_hash: [
    ['engine_descriptor_content_hash'],
    ['prediction_engine', 'content_hash'],
  ],
  commandability_approval_sha256: [
    ['commandability_approval_sha256'],
    ['commandability_approval', 'content_hash'],
  ],
  capability_release_id: [
    ['capability_release_id'],
    ['commandability_approval', 'device_capability', 'capability_release_id'],
  ],
  capability_hash: [
    ['capability_hash'],
    ['commandability_approval', 'device_capability', 'capability_hash'],
  ],
} as const;

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function safeIdentifier(value: string): boolean {
  return SAFE_VALUE.test(value) && !SENSITIVE_MARKER.test(value);
}

function atPath(value: unknown, keys: readonly string[]): unknown {
  let current: unknown = value;
  for (const key of keys) {
    const currentRecord = record(current);
    if (!currentRecord) return undefined;
    current = currentRecord[key];
  }
  return current;
}

function safeReadiness(value: unknown): Record<string, unknown> | undefined {
  const source = record(value);
  if (!source) return undefined;
  const result: Record<string, unknown> = {};
  if (
    Number.isInteger(source.http_status) &&
    (source.http_status as number) >= 100 &&
    (source.http_status as number) <= 599
  ) {
    result.http_status = source.http_status;
  }
  for (const key of ['status', 'service']) {
    if (typeof source[key] === 'string' && safeIdentifier(source[key] as string)) {
      result[key] = source[key];
    }
  }
  const checks = record(source.checks);
  if (checks) {
    const selected: Record<string, string> = {};
    for (const key of ['migrations', 'control_tables', 'redis', 'dispatch_worker']) {
      const value = checks[key];
      if (typeof value === 'string' && safeIdentifier(value)) selected[key] = value;
    }
    if (Object.keys(selected).length > 0) result.checks = selected;
  }
  return Object.keys(result).length > 0 ? result : undefined;
}

function safeMetricLines(exposition: string): string[] {
  const allowedNames =
    /^(scheduler_metrics_scrape_error|scheduler_dispatch_worker_heartbeat_(present|age_seconds)|control_(plan_runs_total|prediction_runs_total|intent_validations_total|authority_grant_events_total|command_executions_total)|command_intent_(rejections_total|lag_seconds|dispatch_pending)|gate_readback_mismatch_total|machine_(modbus_writes_total|execution_outcomes_total))$/;
  return exposition
    .split(/\r?\n/u)
    .filter(line => {
      if (line.length === 0 || line.length > 2_048 || SENSITIVE_MARKER.test(line)) {
        return false;
      }
      const match = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+0-9.eENaInf]+)$/u.exec(line);
      if (!match || !allowedNames.test(match[1])) return false;
      if (match[2] && !/^[A-Za-z0-9_=".,:()/-]+$/u.test(match[2])) return false;
      return true;
    })
    .slice(0, MAX_METRIC_LINES);
}

function safeReleaseIdentity(value: unknown): Record<string, string | number> {
  const result: Record<string, string | number> = {};
  for (const [name, paths] of Object.entries(RELEASE_STRING_PATHS)) {
    const candidate = paths.map(keys => atPath(value, keys)).find(item => typeof item === 'string');
    if (typeof candidate === 'string' && safeIdentifier(candidate)) result[name] = candidate;
  }
  const envelope = record(atPath(value, ['action_model', 'operating_envelope'])) ?? record(value);
  if (envelope) {
    const names = [
      'minimum_flow_m3s',
      'maximum_flow_m3s',
      'flow_lower_exclusive_m3s',
      'flow_upper_inclusive_m3s',
    ];
    for (const name of names) {
      const candidate = envelope[name];
      if (typeof candidate === 'number' && Number.isFinite(candidate)) result[name] = candidate;
    }
  }
  return result;
}

export function buildSafeEvidence(input: SafeEvidenceInput) {
  if (!COMMIT_SHA.test(input.commit)) throw new Error('commit must be a full lowercase SHA');
  const migrations = input.migrations.map(row => {
    if (
      typeof row.migration_id !== 'string' ||
      !safeIdentifier(row.migration_id) ||
      typeof row.checksum !== 'string' ||
      !SHA256.test(row.checksum)
    ) {
      throw new Error('invalid migration evidence');
    }
    return { migration_id: row.migration_id, checksum: row.checksum };
  });
  const processes = input.pm2.flatMap(item => {
    const source = record(item);
    const environment = record(source?.pm2_env);
    if (
      !source ||
      !environment ||
      typeof source.name !== 'string' ||
      !safeIdentifier(source.name)
    ) {
      return [];
    }
    const cwd = environment.pm_cwd;
    return [
      {
        name: source.name,
        status:
          typeof environment.status === 'string' && safeIdentifier(environment.status)
            ? environment.status
            : 'unknown',
        pid: Number.isInteger(source.pid) && (source.pid as number) >= 0 ? source.pid : null,
        restarts:
          Number.isInteger(environment.restart_time) && (environment.restart_time as number) >= 0
            ? environment.restart_time
            : null,
        cwd: typeof cwd === 'string' && cwd.length <= 512 && !/[\r\n@]/u.test(cwd) ? cwd : null,
      },
    ];
  });
  const readiness = Object.fromEntries(
    Object.entries(input.readiness).flatMap(([service, value]) => {
      const selected = safeIdentifier(service) ? safeReadiness(value) : undefined;
      return selected ? [[service, selected]] : [];
    }),
  );
  const metrics = Object.fromEntries(
    Object.entries(input.metrics)
      .filter(([service]) => safeIdentifier(service))
      .map(([service, exposition]) => [service, safeMetricLines(exposition)]),
  );
  const artifactHashes = Object.entries(input.artifactHashes).flatMap(
    ([artifact, checksum], index) => {
      if (!SHA256.test(checksum)) return [];
      const basename = path.basename(artifact);
      return [
        {
          artifact: safeIdentifier(basename) ? basename : `artifact-${index + 1}`,
          sha256: checksum,
        },
      ];
    },
  );
  const sourceCounts = record(input.counts) ?? {};
  const counts = Object.fromEntries(
    COUNT_KEYS.flatMap(name => {
      const value = sourceCounts[name];
      return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
        ? [[name, value]]
        : [];
    }),
  );
  return {
    ...(input.collectedAt && UTC_INSTANT.test(input.collectedAt)
      ? { collected_at: input.collectedAt }
      : {}),
    commit: input.commit,
    role: input.role,
    migrations,
    processes,
    readiness,
    metrics,
    artifact_hashes: artifactHashes,
    release_identity: safeReleaseIdentity(input.releaseIdentity),
    counts,
    unavailable: Object.keys(input.unavailable)
      .filter(name => safeIdentifier(name))
      .sort(),
  };
}
