import * as path from 'path';
import { validateDeploymentPreflight } from '../deployment-preflight';
import { readTrackedMigrationManifest } from '../migration-manifest';

const releaseSha = 'a'.repeat(40);
const trackedMigrations = {
  '0012_authority_grants': 'b'.repeat(64),
  '0013_operator_approved_execution': 'c'.repeat(64),
};

const centralInput = {
  role: 'central' as const,
  expectedCommit: releaseSha,
  actualCommit: releaseSha,
  trackedTreeClean: true,
  trackedMigrations,
  appliedMigrations: trackedMigrations,
  requiredFiles: {
    'services/scheduler/start.sh': true,
    'services/scheduler/src/jobs/shadow_dispatch_once.py': true,
  },
  processes: [
    {
      name: 'scheduler',
      script: './start.sh',
      env: { CONTROL_EXECUTION_MODE: 'disabled' },
    },
    {
      name: 'scheduler-control-dispatch',
      script: './venv/bin/python',
      args: '-m jobs.shadow_dispatch_once',
      autorestart: true,
      restart_delay: 60_000,
      env: { CONTROL_EXECUTION_MODE: 'disabled' },
    },
  ],
};

describe('validateDeploymentPreflight', () => {
  test('current-main migration manifest is complete through 0013', () => {
    const manifest = readTrackedMigrationManifest(path.resolve(__dirname, '../../..'));
    expect(manifest['0013_operator_approved_execution']).toBe(
      'b8c133460303d75a2a69026a0072bf708125e75434d56c613b642241d2bfed1a',
    );
  });

  test('accepts an exact release with migration 0013 and the bounded dark worker', () => {
    expect(validateDeploymentPreflight(centralInput)).toEqual(
      expect.objectContaining({
        approved: true,
        commit: releaseSha,
        latestMigration: '0013_operator_approved_execution',
        processNames: ['scheduler', 'scheduler-control-dispatch'],
      }),
    );
  });

  test('rejects a stale binary even if its old schema reports ready', () => {
    expect(() =>
      validateDeploymentPreflight({
        ...centralInput,
        actualCommit: 'd'.repeat(40),
      }),
    ).toThrow('release commit mismatch');
  });

  test('rejects a stale schema missing migration 0013', () => {
    expect(() =>
      validateDeploymentPreflight({
        ...centralInput,
        appliedMigrations: { '0012_authority_grants': 'b'.repeat(64) },
      }),
    ).toThrow('migration manifest mismatch');
  });

  test('rejects checksum drift, a dirty release, missing binaries, or an unbounded worker', () => {
    expect(() =>
      validateDeploymentPreflight({
        ...centralInput,
        appliedMigrations: {
          ...trackedMigrations,
          '0013_operator_approved_execution': 'd'.repeat(64),
        },
      }),
    ).toThrow('migration manifest mismatch');
    expect(() => validateDeploymentPreflight({ ...centralInput, trackedTreeClean: false })).toThrow(
      'tracked release tree is dirty',
    );
    expect(() =>
      validateDeploymentPreflight({
        ...centralInput,
        requiredFiles: { 'services/scheduler/start.sh': false },
      }),
    ).toThrow('required release file is missing');
    expect(() =>
      validateDeploymentPreflight({
        ...centralInput,
        processes: centralInput.processes.map(process =>
          process.name === 'scheduler-control-dispatch'
            ? { ...process, restart_delay: 0 }
            : process,
        ),
      }),
    ).toThrow('bounded dispatch worker topology mismatch');
  });

  test('accepts only the dedicated dark SCADA process for a field release', () => {
    expect(
      validateDeploymentPreflight({
        role: 'field',
        expectedCommit: releaseSha,
        actualCommit: releaseSha,
        trackedTreeClean: true,
        trackedMigrations: {},
        appliedMigrations: {},
        requiredFiles: { 'services/scada-gate-control/dist/index.js': true },
        processes: [
          {
            name: 'scada-gate-control',
            script: 'dist/index.js',
            env: { ALLOW_MACHINE_COMMANDS: 'false' },
          },
        ],
      }),
    ).toMatchObject({
      approved: true,
      processNames: ['scada-gate-control'],
      commandGates: { ALLOW_MACHINE_COMMANDS: 'false' },
    });
  });

  test('rejects the legacy SCADA service and any armed field topology', () => {
    const fieldInput = {
      role: 'field' as const,
      expectedCommit: releaseSha,
      actualCommit: releaseSha,
      trackedTreeClean: true,
      trackedMigrations: {},
      appliedMigrations: {},
      requiredFiles: { 'services/scada-gate-control/dist/index.js': true },
      processes: [
        {
          name: 'scada-gate-control',
          script: 'dist/index.js',
          env: { ALLOW_MACHINE_COMMANDS: 'false' },
        },
      ],
    };
    expect(() =>
      validateDeploymentPreflight({
        ...fieldInput,
        processes: [...fieldInput.processes, { name: 'scada-service', script: 'npm' }],
      }),
    ).toThrow('legacy scada-service');
    expect(() =>
      validateDeploymentPreflight({
        ...fieldInput,
        processes: [
          {
            ...fieldInput.processes[0],
            env: { ALLOW_MACHINE_COMMANDS: 'true' },
          },
        ],
      }),
    ).toThrow('not dark');
  });

  test('rejects empty file evidence or duplicate control process names', () => {
    expect(() => validateDeploymentPreflight({ ...centralInput, requiredFiles: {} })).toThrow(
      'required release file is missing',
    );
    expect(() =>
      validateDeploymentPreflight({
        ...centralInput,
        processes: [...centralInput.processes, centralInput.processes[0]],
      }),
    ).toThrow('scheduler process must be unique');
  });
});
