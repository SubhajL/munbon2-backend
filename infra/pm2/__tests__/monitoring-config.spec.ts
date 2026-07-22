import * as fs from 'fs';
import * as path from 'path';

const repoRoot = path.resolve(__dirname, '../../..');
const prometheus = fs.readFileSync(
  path.join(repoRoot, 'infra', 'monitoring', 'control-plane-prometheus.yml'),
  'utf8',
);
const rules = fs.readFileSync(
  path.join(repoRoot, 'infra', 'monitoring', 'control-plane-alerts.yml'),
  'utf8',
);
const workflow = fs.readFileSync(
  path.join(repoRoot, '.github', 'workflows', 'control-plane-hardening-tests.yml'),
  'utf8',
);

describe('control-plane monitoring configuration', () => {
  test('scrapes Scheduler and SCADA metrics plus their safe readiness endpoints', () => {
    expect(prometheus).toContain('job_name: scheduler-control-plane');
    expect(prometheus).toContain('job_name: scada-gate-control');
    expect(prometheus).toContain('job_name: control-plane-readiness');
    expect(prometheus).toContain('/etc/prometheus/control-plane-central-targets.json');
    expect(prometheus).toContain('/etc/prometheus/control-plane-field-targets.json');
    expect(prometheus).toContain('/etc/prometheus/control-plane-readiness-targets.json');
    expect(prometheus).toContain('control-plane-alerts.yml');
  });

  test('alerts on every commissioning control-plane failure signal', () => {
    const signals = [
      'probe_success',
      'up{job=~"scheduler-control-plane|scada-gate-control"}',
      'scheduler_dispatch_worker_heartbeat_present',
      'scheduler_metrics_scrape_error',
      'command_intent_rejections_total',
      'gate_readback_mismatch_total',
      'status="execution_in_doubt"',
      'machine_modbus_writes_total{mode="shadow"}',
      'absent(control_command_executions_total)',
      'absent(machine_execution_outcomes_total)',
    ];
    expect(signals.every(signal => rules.includes(signal))).toBe(true);
  });

  test('routes deployment and monitoring changes through the PM2 infrastructure gate', () => {
    expect(workflow).toContain('infra/pm2/**');
    expect(workflow).toContain('infra/monitoring/**');
    expect(workflow).toContain('pm2-infrastructure-tests:');
    expect(workflow).toContain('npm run verify');
  });
});
