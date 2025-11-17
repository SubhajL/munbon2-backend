const { buildPlotConfigsFromEnriched } = require('../plotConfigBuilder');

describe('buildPlotConfigsFromEnriched', () => {
  test('includes AWD-only plots and assigns correct sensorId', () => {
    const plots = [
      { plot_id: 'P1', crop_type: 'rice', control_mode: 'MOISTURE', area_rai: 2.5, solenoid_valve: 'SV_P1' },
      { plot_id: 'P2', crop_type: 'rice', control_mode: 'AWD', area_rai: 3.0, solenoid_valve: null }
    ];

    const mappings = [
      { plot_id: 'P1', sensor_type: 'moisture', sensor_id: 'MOIST-1' },
      { plot_id: 'P2', sensor_type: 'water_level', sensor_id: 'WL-2' }
    ];

    const result = buildPlotConfigsFromEnriched({ plots, mappings, deviceOverrides: null });

    const p1 = result.plots.find(p => p.plotId === 'P1');
    const p2 = result.plots.find(p => p.plotId === 'P2');

    expect(p1.sensorId).toBe('MOIST-1');
    expect(p2.sensorId).toBe('WL-2');
    expect(result.valveMapping.get('P1')).toBe('SV_P1');
    expect(result.valveMapping.get('P2')).toMatch(/^SV_/); // defaulted
  });

  test('sets areaRai and valveName from views when present', () => {
    const plots = [
      { plot_id: 'P3', crop_type: 'rice', control_mode: 'MOISTURE', area_rai: 1.13, solenoid_valve: 'SV_SF03' }
    ];
    const mappings = [
      { plot_id: 'P3', sensor_type: 'moisture', sensor_id: 'MS-3' },
      { plot_id: 'P3', sensor_type: 'water_level', sensor_id: 'WL-3' }
    ];

    const result = buildPlotConfigsFromEnriched({ plots, mappings, deviceOverrides: null });
    const p3 = result.plots[0];

    expect(p3.areaRai).toBe(1.13);
    expect(p3.valveName).toBe('SV_SF03');
  });
});