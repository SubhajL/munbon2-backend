import * as path from 'path';

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function assessPm2Processes(
  rawProcesses: readonly unknown[],
  expectedCwds: Readonly<Record<string, string>>,
): { processes: unknown[]; unavailable: string[] } {
  const expectedNames = new Set(Object.keys(expectedCwds));
  const processes = rawProcesses.filter(item => {
    const source = record(item);
    return typeof source?.name === 'string' && expectedNames.has(source.name);
  });
  const unavailable: string[] = [];
  for (const [name, expectedCwd] of Object.entries(expectedCwds)) {
    const matches = processes.filter(item => record(item)?.name === name);
    if (matches.length === 0) {
      unavailable.push(`pm2_missing_${name}`);
      continue;
    }
    if (matches.length > 1) unavailable.push(`pm2_duplicate_${name}`);
    const environment = record(record(matches[0])?.pm2_env);
    if (environment?.status !== 'online') unavailable.push(`pm2_status_${name}`);
    const cwd = environment?.pm_cwd;
    if (typeof cwd !== 'string' || path.resolve(cwd) !== path.resolve(expectedCwd)) {
      unavailable.push(`pm2_cwd_${name}`);
    }
  }
  return { processes, unavailable: unavailable.sort() };
}
