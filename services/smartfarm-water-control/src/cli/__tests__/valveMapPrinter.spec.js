const { fetchValveMapAndFormat } = require('../valveMapPrinter');

describe('valveMapPrinter', () => {
  test('prints table from DB rows', async () => {
    const repo = {
      getAllValvePlotMappings: jest.fn().mockResolvedValue([
        { plotId: 'SF-L1', valveName: 'SV-L1' },
        { plotId: 'SF-U1', valveName: 'SV-U1' }
      ])
    };

    const text = await fetchValveMapAndFormat({ repo, json: false, onlyScada: false, plotsPattern: 'SF-*' });
    expect(text).toMatch(/Plot\s+SmartFarm Valve\s+SCADA Valve/);
    expect(text).toMatch(/SF-L1\s+SV-L1\s+SV_L/);
    expect(text).toMatch(/SF-U1\s+SV-U1\s+SV_C1_L/);
  });

  test('prints JSON when requested', async () => {
    const repo = { getAllValvePlotMappings: jest.fn().mockResolvedValue([{ plotId: 'SF-U1', valveName: 'SV-U1' }]) };
    const json = await fetchValveMapAndFormat({ repo, json: true, onlyScada: true, plotsPattern: 'SF-U*' });
    const obj = JSON.parse(json);
    expect(obj).toEqual([{ plotId: 'SF-U1', scadaValve: 'SV_C1_L' }]);
  });
});