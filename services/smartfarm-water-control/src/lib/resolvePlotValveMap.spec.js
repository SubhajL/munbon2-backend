const { resolvePlotToValveMap, toScadaValveName } = require('./resolvePlotValveMap');

describe('resolvePlotValveMap', () => {
  test('maps SF-* plot to SmartFarm and SCADA valves', () => {
    const mappingJson = {
      plot_device_mapping: {
        'SF-U1': { devices: { solenoid_valve: 'SV-U1' } },
        'some-uuid-123': { devices: { solenoid_valve: 'SV-L3' } }
      }
    };

    const rows = resolvePlotToValveMap({ mappingJson, onlySF: true });
    expect(rows).toEqual([
      { plotKey: 'SF-U1', valveId: 'SV-U1', scadaValve: 'SV_C1_L' }
    ]);
  });

  test('SCADA mapping returns null for unknown valves', () => {
    expect(toScadaValveName('SV-UNKNOWN')).toBeNull();
  });
});