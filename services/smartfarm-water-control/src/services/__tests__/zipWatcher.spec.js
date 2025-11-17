const { describe, it, expect } = require('@jest/globals');
jest.mock('../unzipAndParse', () => ({ unzipAndParse: jest.fn(async () => ({ count: 2 })) }));
jest.mock('adm-zip', () => {
  return function() { return { extractAllTo: () => {} }; };
}, { virtual: true });

const fs = require('fs');
const path = require('path');

const { ZipWatcher } = require('../zipWatcher');

describe('ZipWatcher.onFile', () => {
  it('moves file to processed on success', async () => {
    const tmpDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'sf-zip-'));
    const processed = path.join(tmpDir, 'processed');
    const failed = path.join(tmpDir, 'failed');
    fs.mkdirSync(processed); fs.mkdirSync(failed);
    const zipPath = path.join(tmpDir, '20250101-moisturesensors.zip');
    fs.writeFileSync(zipPath, 'fake');

    const watcher = new ZipWatcher({ dir: tmpDir, logger: console });
    await watcher.onFile(zipPath);

    expect(fs.existsSync(path.join(processed, '20250101-moisturesensors.zip'))).toBe(true);
  });
});
