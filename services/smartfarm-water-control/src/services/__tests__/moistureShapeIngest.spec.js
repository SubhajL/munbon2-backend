const { describe, it, expect, beforeEach } = require('@jest/globals');
const fs = require('fs');
const path = require('path');

jest.mock('shapefile', () => ({
  open: jest.fn(async () => {
    let i = 0;
    const items = [
      { value: { geometry: { type: 'Point', coordinates: [102.15, 14.49] }, properties: { device_id: '00000011', device_name: 'H-P1-00000011' } }, done: false },
      { done: true }
    ];
    return { read: async () => items[i++] };
  })
}));

const { MoistureShapeIngest } = require('../moistureShapeIngest');

describe('MoistureShapeIngest', () => {
  let repo;
  beforeEach(() => {
    repo = { upsertSensorLocation: jest.fn().mockResolvedValue({}) };
  });

  it('imports points from SHP directory and upserts', async () => {
    const svc = new MoistureShapeIngest({ repo });
    const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sf-test-'));
    fs.writeFileSync(path.join(tmp, 'sensors.shp'), '');
    fs.writeFileSync(path.join(tmp, 'sensors.dbf'), '');

    const count = await svc._importFromDir(tmp);
    expect(count).toBe(1);
    expect(repo.upsertSensorLocation).toHaveBeenCalledWith(expect.objectContaining({ deviceId: '00000011', deviceType: 'moisture_sensor' }));
  });
});