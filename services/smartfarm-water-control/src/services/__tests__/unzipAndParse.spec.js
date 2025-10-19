const { describe, it, expect } = require('@jest/globals');

jest.mock('adm-zip', () => {
  return function() { return { extractAllTo: () => {} }; };
}, { virtual: true });

jest.mock('../moistureShapeIngest', () => ({
  MoistureShapeIngest: class {
    constructor() {}
    async _importFromDir() { return 3; }
  }
}));

const fs = require('fs');
const path = require('path');
const os = require('os');
const { unzipAndParse } = require('../unzipAndParse');

describe('unzipAndParse', () => {
  it('rejects wrong filename', async () => {
    const bad = require('path').join(require('os').tmpdir(), 'bad.zip');
    require('fs').writeFileSync(bad, 'fake');
    await expect(unzipAndParse(bad)).rejects.toThrow(/pattern/);
  });

  it('extracts and imports sensors', async () => {
    const zipPath = path.join(os.tmpdir(), '20250101-moisturesensors.zip');
    fs.writeFileSync(zipPath, 'fake');
    const res = await unzipAndParse(zipPath);
    expect(res.count).toBe(3);
    expect(fs.existsSync(res.tempDir)).toBe(true);
  });
});