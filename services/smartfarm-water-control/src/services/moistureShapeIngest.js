const shapefile = require('shapefile');
const fs = require('fs');
const path = require('path');
const os = require('os');

class MoistureShapeIngest {
  constructor({ repo, logger }) {
    this.repo = repo;
    this.logger = logger || console;
  }

  async importZip(zipPath) {
    // Expect ZIP already extracted by ops; for unit tests we bypass unzip.
    // Find *.shp in the given directory (zipPath may be a dir in tests)
    const dir = path.extname(zipPath).toLowerCase() === '.zip' ? path.join(os.tmpdir(), 'sf-shape') : zipPath;
    if (fs.existsSync(zipPath) && fs.lstatSync(zipPath).isDirectory()) {
      return this._importFromDir(zipPath);
    }
    // If .zip handling is needed, we would extract here; omitted for unit scope.
    throw new Error('ZIP extraction not implemented in test scope; pass a directory path');
  }

  async _importFromDir(dirPath) {
    const shp = fs.readdirSync(dirPath).find(f => f.toLowerCase().endsWith('.shp'));
    if (!shp) throw new Error('No SHP in directory');
    const shpPath = path.join(dirPath, shp);
    const dbfPath = shpPath.replace(/\.shp$/i, '.dbf');

    const source = await shapefile.open(shpPath, dbfPath);
    let rec;
    const upserts = [];
    while (!(rec = await source.read()).done) {
      const { geometry, properties } = rec.value;
      if (!geometry || geometry.type !== 'Point') continue;
      const [lng, lat] = geometry.coordinates;
      const deviceId = properties.device_id || properties.DEVICE_ID || properties.id || properties.ID;
      const deviceName = properties.device_name || properties.DEVICE_NAME || deviceId;
      if (!deviceId || typeof lng !== 'number' || typeof lat !== 'number') continue;
      upserts.push({ deviceId, deviceName, lng, lat });
    }

    for (const s of upserts) {
      await this.repo.upsertSensorLocation({ deviceId: s.deviceId, deviceName: s.deviceName, deviceType: 'moisture_sensor', lng: s.lng, lat: s.lat });
    }
    return upserts.length;
  }
}

module.exports = { MoistureShapeIngest };