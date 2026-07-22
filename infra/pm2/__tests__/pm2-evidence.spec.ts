import { assessPm2Processes } from '../pm2-evidence';

describe('assessPm2Processes', () => {
  test('reports missing, stopped, and stale-release processes without exposing environments', () => {
    const result = assessPm2Processes(
      [
        {
          name: 'scheduler',
          pm2_env: { status: 'online', pm_cwd: '/release/services/scheduler' },
        },
        {
          name: 'scheduler-control-dispatch',
          pm2_env: { status: 'stopped', pm_cwd: '/old-release/services/scheduler' },
        },
      ],
      {
        scheduler: '/release/services/scheduler',
        'scheduler-control-dispatch': '/release/services/scheduler',
        'flow-monitoring': '/release/services/flow-monitoring',
      },
    );

    expect(result.processes.map(process => (process as { name: string }).name)).toEqual([
      'scheduler',
      'scheduler-control-dispatch',
    ]);
    expect(result.unavailable).toEqual([
      'pm2_cwd_scheduler-control-dispatch',
      'pm2_missing_flow-monitoring',
      'pm2_status_scheduler-control-dispatch',
    ]);
  });
});
