const fs = require('fs');
const path = require('path');
const { seedValveMapFromJson, parseMappingFile } = require('../seedValveMapFromJson');

describe('seedValveMapFromJson', () => {
  test('parseMappingFile extracts SF-* solenoid valves', () => {
    const tmp = path.join(__dirname, 'device-mapping.tmp.json');
    const json = {
      plot_device_mapping: {
        'SF-U1': { devices: { solenoid_valve: 'SV-U1' } },
        'SF-L2': { devices: { solenoid_valve: 'SV-L2' } },
        'UUID-XYZ': { devices: { solenoid_valve: 'SV-ZZ' } }
      }
    };
    fs.writeFileSync(tmp, JSON.stringify(json));

    const pairs = parseMappingFile(tmp);
    fs.unlinkSync(tmp);

    expect(pairs).toEqual([
      { plotId: 'SF-U1', valveName: 'SV-U1' },
      { plotId: 'SF-L2', valveName: 'SV-L2' }
    ]);
  });

  test('seedValveMapFromJson upserts each pair', async () => {
    const tmp = path.join(__dirname, 'device-mapping.tmp.json');
    const json = { plot_device_mapping: { 'SF-U1': { devices: { solenoid_valve: 'SV-U1' } } } };
    fs.writeFileSync(tmp, JSON.stringify(json));

    const repo = { upsertValvePlotMapping: jest.fn().mockResolvedValue(undefined) };
    const result = await seedValveMapFromJson({ filePath: tmp, repo, updatedBy: 'test' });
    fs.unlinkSync(tmp);
    expect(repo.upsertValvePlotMapping).toHaveBeenCalledWith({ plotId: 'SF-U1', valveName: 'SV-U1', updatedBy: 'test' });
    expect(result).toEqual({ created: 1 });
  });
});