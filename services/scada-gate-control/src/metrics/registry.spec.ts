import { describe, expect, test } from 'vitest';
import { createScadaMetrics } from './registry';
import { readSeriesValue } from './exposition.test-helpers';

describe('createScadaMetrics', () => {
  test('exposes both roadmap metrics in Prometheus text format', async () => {
    const metrics = createScadaMetrics();
    const body = await metrics.render();
    expect(metrics.contentType).toContain('text/plain');
    expect(body).toContain('# TYPE machine_modbus_writes_total counter');
    expect(body).toContain('# TYPE command_intent_rejections_total counter');
    expect(body).toContain('# TYPE machine_execution_outcomes_total counter');
  });

  test('pre-registers every bounded execution outcome series at 0', async () => {
    const body = await createScadaMetrics().render();
    for (const purpose of ['operator_approved', 'fail_safe_close']) {
      for (const status of [
        'execution_succeeded',
        'execution_rejected',
        'execution_failed',
        'readback_mismatch',
        'execution_in_doubt',
      ]) {
        expect(
          readSeriesValue(
            body,
            `machine_execution_outcomes_total{purpose="${purpose}",status="${status}"}`,
          ),
        ).toBe(0);
      }
    }
  });

  test('recordExecutionOutcome increments only the exact status and purpose series', async () => {
    const metrics = createScadaMetrics();
    metrics.recordExecutionOutcome('execution_succeeded', 'operator_approved');
    const body = await metrics.render();
    expect(
      readSeriesValue(
        body,
        'machine_execution_outcomes_total{purpose="operator_approved",status="execution_succeeded"}',
      ),
    ).toBe(1);
    expect(
      readSeriesValue(
        body,
        'machine_execution_outcomes_total{purpose="fail_safe_close",status="execution_succeeded"}',
      ),
    ).toBe(0);
  });

  test('pre-registers every write-provenance series and schema_invalid at 0 (present, not absent)', async () => {
    const body = await createScadaMetrics().render();
    expect(readSeriesValue(body, 'machine_modbus_writes_total{mode="operator"}')).toBe(0);
    expect(readSeriesValue(body, 'machine_modbus_writes_total{mode="shadow"}')).toBe(0);
    expect(readSeriesValue(body, 'machine_modbus_writes_total{mode="operator_approved"}')).toBe(0);
    expect(readSeriesValue(body, 'command_intent_rejections_total{reason="schema_invalid"}')).toBe(
      0,
    );
  });

  test('recordModbusWrite increments only the given provenance series', async () => {
    const metrics = createScadaMetrics();
    metrics.recordModbusWrite('operator');
    metrics.recordModbusWrite('operator');
    const body = await metrics.render();
    expect(readSeriesValue(body, 'machine_modbus_writes_total{mode="operator"}')).toBe(2);
    expect(readSeriesValue(body, 'machine_modbus_writes_total{mode="shadow"}')).toBe(0);
    expect(readSeriesValue(body, 'machine_modbus_writes_total{mode="operator_approved"}')).toBe(0);
  });

  test('recordSchemaInvalidRejection increments the schema_invalid reason', async () => {
    const metrics = createScadaMetrics();
    metrics.recordSchemaInvalidRejection();
    const body = await metrics.render();
    expect(readSeriesValue(body, 'command_intent_rejections_total{reason="schema_invalid"}')).toBe(
      1,
    );
  });

  test('each build is an isolated registry — counters do not leak across instances', async () => {
    const a = createScadaMetrics();
    const b = createScadaMetrics();
    a.recordModbusWrite('operator');
    a.recordSchemaInvalidRejection();
    const bodyB = await b.render();
    expect(readSeriesValue(bodyB, 'machine_modbus_writes_total{mode="operator"}')).toBe(0);
    expect(readSeriesValue(bodyB, 'command_intent_rejections_total{reason="schema_invalid"}')).toBe(
      0,
    );
  });
});
