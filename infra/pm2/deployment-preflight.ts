export type DeploymentRole = 'central' | 'field';

export type DeploymentProcess = {
  readonly name: string;
  readonly script: string;
  readonly args?: string;
  readonly autorestart?: boolean;
  readonly restart_delay?: number;
  readonly env?: Record<string, string>;
};

export type DeploymentPreflightInput = {
  readonly role: DeploymentRole;
  readonly expectedCommit: string;
  readonly actualCommit: string;
  readonly trackedTreeClean: boolean;
  readonly trackedMigrations: Readonly<Record<string, string>>;
  readonly appliedMigrations: Readonly<Record<string, string>>;
  readonly requiredFiles: Readonly<Record<string, boolean>>;
  readonly processes: readonly DeploymentProcess[];
};

export type DeploymentPreflightReport = {
  readonly approved: true;
  readonly role: DeploymentRole;
  readonly commit: string;
  readonly latestMigration: string | null;
  readonly processNames: readonly string[];
  readonly commandGates: Readonly<Record<string, 'disabled' | 'false'>>;
};

const SHA256 = /^[0-9a-f]{64}$/;
const COMMIT_SHA = /^[0-9a-f]{40}$/;
const REQUIRED_EXECUTION_MIGRATION = '0013_operator_approved_execution';

function assertMigrationParity(
  tracked: Readonly<Record<string, string>>,
  applied: Readonly<Record<string, string>>,
): string[] {
  const trackedEntries = Object.entries(tracked).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  const appliedEntries = Object.entries(applied).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  if (
    trackedEntries.length === 0 ||
    !trackedEntries.some(([migrationId]) => migrationId === REQUIRED_EXECUTION_MIGRATION) ||
    trackedEntries.some(([, checksum]) => !SHA256.test(checksum)) ||
    JSON.stringify(trackedEntries) !== JSON.stringify(appliedEntries)
  ) {
    throw new Error('migration manifest mismatch');
  }
  return trackedEntries.map(([migrationId]) => migrationId);
}

function processNamed(processes: readonly DeploymentProcess[], name: string): DeploymentProcess {
  const matches = processes.filter(candidate => candidate.name === name);
  if (matches.length !== 1) throw new Error(`required ${name} process must be unique`);
  return matches[0];
}

export function validateDeploymentPreflight(
  input: DeploymentPreflightInput,
): DeploymentPreflightReport {
  if (!COMMIT_SHA.test(input.expectedCommit) || !COMMIT_SHA.test(input.actualCommit)) {
    throw new Error('release commit must be a full lowercase SHA');
  }
  if (input.expectedCommit !== input.actualCommit) throw new Error('release commit mismatch');
  if (!input.trackedTreeClean) throw new Error('tracked release tree is dirty');
  if (
    Object.keys(input.requiredFiles).length === 0 ||
    Object.values(input.requiredFiles).some(present => !present)
  ) {
    throw new Error('required release file is missing');
  }

  if (input.role === 'central') {
    const migrationIds = assertMigrationParity(input.trackedMigrations, input.appliedMigrations);
    const scheduler = processNamed(input.processes, 'scheduler');
    const worker = processNamed(input.processes, 'scheduler-control-dispatch');
    if (scheduler.env?.CONTROL_EXECUTION_MODE !== 'disabled') {
      throw new Error('scheduler execution gate is not dark');
    }
    if (
      worker.script !== './venv/bin/python' ||
      worker.args !== '-m jobs.shadow_dispatch_once' ||
      worker.autorestart !== true ||
      worker.restart_delay !== 60_000 ||
      worker.env?.CONTROL_EXECUTION_MODE !== 'disabled'
    ) {
      throw new Error('bounded dispatch worker topology mismatch');
    }
    return {
      approved: true,
      role: input.role,
      commit: input.actualCommit,
      latestMigration: migrationIds.at(-1) ?? null,
      processNames: [scheduler.name, worker.name],
      commandGates: { CONTROL_EXECUTION_MODE: 'disabled' },
    };
  }

  if (Object.keys(input.appliedMigrations).length > 0) {
    throw new Error('field preflight does not accept Scheduler migration evidence');
  }
  const scada = processNamed(input.processes, 'scada-gate-control');
  if (input.processes.some(candidate => candidate.name === 'scada-service')) {
    throw new Error('legacy scada-service cannot satisfy the machine-boundary topology');
  }
  if (scada.script !== 'dist/index.js' || scada.env?.ALLOW_MACHINE_COMMANDS !== 'false') {
    throw new Error('SCADA machine-boundary topology is not dark');
  }
  return {
    approved: true,
    role: input.role,
    commit: input.actualCommit,
    latestMigration: null,
    processNames: [scada.name],
    commandGates: { ALLOW_MACHINE_COMMANDS: 'false' },
  };
}
