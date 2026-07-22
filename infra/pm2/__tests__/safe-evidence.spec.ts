import { buildSafeEvidence } from '../safe-evidence';

describe('buildSafeEvidence', () => {
  test('projects bounded operational evidence without secrets or raw error text', () => {
    const secret = 'never-print-this-secret';
    const evidence = buildSafeEvidence({
      commit: 'a'.repeat(40),
      role: 'central',
      migrations: [
        { migration_id: '0012_authority_grants', checksum: 'b'.repeat(64) },
        {
          migration_id: '0013_operator_approved_execution',
          checksum: 'c'.repeat(64),
        },
      ],
      pm2: [
        {
          name: 'scheduler',
          pid: 123,
          pm2_env: {
            status: 'online',
            restart_time: 2,
            pm_cwd: '/srv/munbon/release-a',
            POSTGRES_URL: `postgresql://user:${secret}@db/munbon`,
          },
        },
      ],
      readiness: {
        scheduler: {
          http_status: 503,
          status: 'ready',
          checks: { migrations: 'ok', control_tables: 'ok', redis: 'ok' },
          debug: secret,
        },
      },
      metrics: {
        scheduler: `scheduler_metrics_scrape_error 0\nsecret_metric{token="${secret}"} 1\n`,
      },
      artifactHashes: { '/secure/d6.json': 'd'.repeat(64) },
      releaseIdentity: {
        model_release_id: 'release-v4',
        flow_lower_exclusive_m3s: 0,
        flow_upper_inclusive_m3s: 11.2,
        hidden: secret,
      },
      counts: {
        control_plan_runs: 0,
        authority_grants: 0,
        grant_events: 0,
        complete_drill_evidence_sets: 0,
        raw_secret_count: secret,
      },
      unavailable: { scada: `connection failed with ${secret}` },
    });

    const rendered = JSON.stringify(evidence);
    expect(rendered).not.toContain(secret);
    expect(evidence).toEqual(
      expect.objectContaining({
        commit: 'a'.repeat(40),
        migrations: expect.arrayContaining([
          expect.objectContaining({
            migration_id: '0013_operator_approved_execution',
          }),
        ]),
        processes: [
          {
            name: 'scheduler',
            status: 'online',
            pid: 123,
            restarts: 2,
            cwd: '/srv/munbon/release-a',
          },
        ],
        readiness: {
          scheduler: {
            http_status: 503,
            status: 'ready',
            checks: { migrations: 'ok', control_tables: 'ok', redis: 'ok' },
          },
        },
        metrics: { scheduler: ['scheduler_metrics_scrape_error 0'] },
        unavailable: ['scada'],
      }),
    );
  });

  test('bounds metrics and rejects malformed commit or migration evidence', () => {
    const common = {
      commit: 'a'.repeat(40),
      role: 'central' as const,
      migrations: [
        {
          migration_id: '0013_operator_approved_execution',
          checksum: 'b'.repeat(64),
        },
      ],
      pm2: [],
      readiness: {},
      metrics: {
        scheduler: Array.from(
          { length: 400 },
          (_, index) => `control_plan_runs_total{status="feasible"} ${index}`,
        ).join('\n'),
      },
      artifactHashes: {},
      releaseIdentity: {},
      counts: {},
      unavailable: {},
    };
    expect(buildSafeEvidence(common).metrics.scheduler).toHaveLength(200);
    expect(() => buildSafeEvidence({ ...common, commit: 'main' })).toThrow('commit');
    expect(() =>
      buildSafeEvidence({
        ...common,
        migrations: [{ migration_id: '0013_operator_approved_execution', checksum: 'bad' }],
      }),
    ).toThrow('migration evidence');
  });

  test('does not trust caller-provided timestamp, artifact names, or unavailable keys', () => {
    const secret = 'never-print-this-secret';
    const evidence = buildSafeEvidence({
      collectedAt: secret,
      commit: 'a'.repeat(40),
      role: 'field',
      migrations: [],
      pm2: [],
      readiness: {},
      metrics: {},
      artifactHashes: { [`/secure/${secret}.json`]: 'b'.repeat(64) },
      releaseIdentity: {},
      counts: {},
      unavailable: { [secret]: true },
    });
    expect(JSON.stringify(evidence)).not.toContain(secret);
    expect(evidence.artifact_hashes).toEqual([{ artifact: 'artifact-1', sha256: 'b'.repeat(64) }]);
    expect(evidence.unavailable).toEqual([]);
  });
});
