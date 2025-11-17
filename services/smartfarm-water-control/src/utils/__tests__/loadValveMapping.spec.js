const { loadValveMappingFromDb } = require('../loadValveMapping');

describe('loadValveMappingFromDb', () => {
  test('builds Map from repo rows', async () => {
    const repo = {
      getAllValvePlotMappings: jest.fn().mockResolvedValue([
        { plotId: 'SF-U1', valveName: 'SV-U1' },
        { plotId: 'SF-L3', valveName: 'SV-L3' }
      ])
    };

    const map = await loadValveMappingFromDb(repo);
    expect(map.get('SF-U1')).toBe('SV-U1');
    expect(map.get('SF-L3')).toBe('SV-L3');
  });
});