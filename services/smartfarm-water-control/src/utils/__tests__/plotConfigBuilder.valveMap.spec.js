const { buildValveMappingFromDb, mergeValveMapping } = require('../plotConfigBuilder');

describe('plotConfigBuilder valve map', () => {
  test('buildValveMappingFromDb builds Map from DAO rows', async () => {
    const repo = {
      getAllValvePlotMappings: jest.fn().mockResolvedValue([
        { plotId: 'SF-U1', valveName: 'SV-U1' },
        { plotId: 'SF-L2', valveName: 'SV-L2' }
      ])
    };
    const map = await buildValveMappingFromDb(repo);
    expect(map.get('SF-U1')).toBe('SV-U1');
    expect(map.get('SF-L2')).toBe('SV-L2');
  });

  test('mergeValveMapping applies DB valves and validates', () => {
    const plots = [
      { plotId: 'SF-U1', controlMode: 'MOISTURE', areaRai: 1.0 },
      { plotId: 'SF-L2', controlMode: 'AWD', areaRai: 1.0 }
    ];
    const dbValveMap = new Map([
      ['SF-U1', 'SV-U1'],
      ['SF-L2', 'SV-L2']
    ]);
    const { plots: out, valveMapping } = mergeValveMapping({ plots, dbValveMap });
    expect(out.find(p => p.plotId === 'SF-U1').valveId).toBe('SV-U1');
    expect(valveMapping.get('SF-L2')).toBe('SV-L2');
  });

  test('mergeValveMapping throws when required valve missing', () => {
    const plots = [ { plotId: 'SF-U1', controlMode: 'MOISTURE', areaRai: 1.0 } ];
    const dbValveMap = new Map();
    expect(() => mergeValveMapping({ plots, dbValveMap })).toThrow(/missing valve mapping/i);
  });
});