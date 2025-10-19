const { describe, it, expect, beforeEach } = require('@jest/globals');
const fs = require('fs');

let ShapeIngestService;

describe('ShapeIngestService (unit)', () => {
  let repo;

  beforeEach(() => {
    repo = {
      upsertPlotBoundary: jest.fn().mockResolvedValue(),
      upsertDevice: jest.fn().mockResolvedValue(),
      upsertSensorLocation: jest.fn().mockResolvedValue(),
      upsertPlotConfiguration: jest.fn().mockResolvedValue(),
      upsertSensorMapping: jest.fn().mockResolvedValue(),
    };
    jest.isolateModules(() => {
      ShapeIngestService = require('../shapeIngestService');
    });
  });

  it('parseGeoJSON validates polygon and area', () => {
    const svc = new ShapeIngestService({ repo });

    const geojson = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { plot_id: 'p1', plot_name: 'Plot 1', area_rai: 1.23 },
          geometry: { type: 'Polygon', coordinates: [[[102,14],[102.01,14],[102.01,14.01],[102,14.01],[102,14]]] }
        }
      ]
    };

    const result = svc.parseGeoJSON(geojson);
    expect(result).toEqual([
      {
        plotId: 'p1',
        plotName: 'Plot 1',
        areaRai: 1.23,
        geojson: geojson.features[0].geometry,
      }
    ]);

    // invalid
    const bad = { type: 'FeatureCollection', features: [{ properties: { plot_id: 'x', area_rai: 0 }, geometry: { type: 'Point', coordinates: [0,0] } }] };
    expect(() => svc.parseGeoJSON(bad)).toThrow(/Polygon/);
  });

  it('parseDeviceMapping extracts devices and assignments', () => {
    const svc = new ShapeIngestService({ repo });
    const mapping = {
      devices: {
        solenoid_valves: [ { device_name: 'SV-U1', coordinates: [102,14] } ],
        flow_meters: [ { device_name: 'F-U1', coordinates: [102,14] } ],
        moisture_sensors: [ { device_name: 'H-P1-0001', device_id: '0001', coordinates: [102,14], position: 1 } ]
      },
      plot_device_mapping: {
        'p1': { devices: { solenoid_valve: 'SV-U1', flow_meter: 'F-U1', moisture_sensor: 'H-P1-0001' }, control_mode: 'AWD', area_rai: 1.23, plot_name: 'Plot 1' }
      }
    };

    const res = svc.parseDeviceMapping(mapping);
    expect(res.devices.solenoid_valves[0].deviceName).toBe('SV-U1');
    expect(res.assignments.get('p1').valveId).toBe('SV-U1');
  });

  it('planChanges prepares ordered upserts', () => {
    const svc = new ShapeIngestService({ repo });
    const plots = [{ plotId: 'p1', plotName: 'Plot 1', areaRai: 1.2, geojson: { type: 'Polygon', coordinates: [[[0,0],[1,0],[1,1],[0,1],[0,0]]] } }];
    const devices = { solenoid_valves: [{ deviceName: 'SV-U1', lng: 102, lat: 14 }], flow_meters: [], moisture_sensors: [] };
    const assignments = new Map([
      ['p1', { valveId: 'SV-U1', flowmeterId: null, sensorId: null, controlMode: 'AWD', areaRai: 1.2 }]
    ]);

    const plan = svc.planChanges({ plots, devices, assignments });
    expect(plan.plotBoundaries).toHaveLength(1);
    expect(plan.devices).toHaveLength(1);
    expect(plan.plotConfigs).toHaveLength(1);
  });

  it('applyUpserts executes in dependency order', async () => {
    const svc = new ShapeIngestService({ repo });
    const plan = {
      plotBoundaries: [{ plotId: 'p1', plotName: 'Plot 1', areaRai: 1.2, geojson: { type: 'Polygon', coordinates: [[[0,0],[1,0],[1,1],[0,1],[0,0]]] } }],
      devices: [{ deviceName: 'SV-U1', deviceType: 'solenoid_valve', zone: 'upper', metadata: {} }],
      sensors: [{ deviceId: '0001', deviceName: 'H-P1-0001', deviceType: 'moisture_sensor', lng: 102, lat: 14, plotId: 'p1' }],
      plotConfigs: [{ plotId: 'p1', cropType: 'rice', controlMode: 'AWD', valveId: 'SV-U1', flowmeterId: null, areaRai: 1.2 }],
      sensorMappings: [{ sensorId: '0001', plotId: 'p1', sensorType: 'moisture' }]
    };

    const summary = await svc.applyUpserts(plan);
    expect(repo.upsertPlotBoundary).toHaveBeenCalled();
    expect(repo.upsertDevice).toHaveBeenCalled();
    expect(repo.upsertSensorLocation).toHaveBeenCalled();
    expect(repo.upsertPlotConfiguration).toHaveBeenCalled();
    expect(repo.upsertSensorMapping).toHaveBeenCalled();
    expect(summary).toEqual({ plotBoundaries: 1, devices: 1, sensors: 1, plotConfigs: 1, sensorMappings: 1 });
  });
});