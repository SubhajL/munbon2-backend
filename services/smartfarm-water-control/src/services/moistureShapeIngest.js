const shapefile = require('shapefile');
const fs = require('fs');
const path = require('path');

class MoistureShapeIngest {
  constructor({ repo, logger, timescaleRepo }) {
    this.repo = repo;
    this.logger = logger || console;
    this.timescaleRepo = timescaleRepo || null;
  }

  async autoMapMoistureSensors(records) {
    const stats = { processed: 0, mapped: 0, updated: 0, skipped: 0 };
    const pairs = [];
    for (const r of records || []) {
      stats.processed += 1;
      const { deviceId, lng, lat } = r;
      if (
        !deviceId ||
        typeof lng !== 'number' ||
        typeof lat !== 'number' ||
        Number.isNaN(lng) ||
        Number.isNaN(lat)
      ) {
        stats.skipped += 1;
        continue;
      }
      const plotId = await this.repo.findPlotByCoordinates(this.repo.pool, lng, lat);
      if (!plotId) {
        stats.skipped += 1;
        continue;
      }
      await this.repo.upsertSensorMapping({ sensorId: deviceId, plotId, sensorType: 'moisture' });
      pairs.push({ sensorId: deviceId, plotId });
      stats.mapped += 1;
      stats.updated += 1; // treat upsert as update-or-create
    }
    return { stats, pairs };
  }

  async importZip(zipPath) {
    // Expect ZIP already extracted by ops; for unit tests we bypass unzip.
    // Find *.shp in the given directory (zipPath may be a dir in tests)
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

    let autoResult = { stats: { processed: 0, mapped: 0, updated: 0, skipped: 0 }, pairs: [] };
    try {
      autoResult = await this.autoMapMoistureSensors(upserts);
      this.logger.info({ stats: autoResult.stats }, 'Auto-mapped moisture sensors to plots');
    } catch (e) {
      this.logger.warn({ error: e }, 'Moisture sensor auto-mapping failed');
    }

    // Prime sensor_plot_readings immediately for affected plots
    try {
      if (this.timescaleRepo) {
        await this.primeMoisturePlotReadings(autoResult.pairs);
      }
    } catch (e) {
      this.logger.warn({ error: e }, 'Failed to prime moisture plot readings');
    }

    return upserts.length;
  }

  async primeMoisturePlotReadings(pairs) {
    // Group sensorIds by plotId
    const byPlot = new Map();
    for (const p of pairs || []) {
      if (!byPlot.has(p.plotId)) byPlot.set(p.plotId, new Set());
      byPlot.get(p.plotId).add(p.sensorId);
    }

    for (const [plotId, newSensorsSet] of byPlot.entries()) {
      // Include all currently mapped sensors for the plot (not only new ones)
      let mappedIds = [];
      try {
        mappedIds = await this.repo.listMappedSensorsForPlot(plotId, 'moisture');
      } catch (e) {
        // fallback to new sensors only if query fails (shouldn’t)
        mappedIds = Array.from(newSensorsSet);
      }
      const uniqueIds = Array.from(new Set([...(mappedIds || []), ...newSensorsSet]));
      if (uniqueIds.length === 0) continue;

      const readings = await this.timescaleRepo.getLatestMoistureReadings(
        this.timescaleRepo.pool || this.timescaleRepo,
        uniqueIds,
        30 * 60 * 1000
      );

      if (!Array.isArray(readings) || readings.length === 0) {
        this.logger.info({ plotId }, 'No fresh moisture readings to seed');
        continue;
      }

      // Prepare aggregate
      const values = readings.map((r) => r.value);
      const timestamps = readings.map((r) => new Date(r.timestamp).getTime());
      const maxTs = new Date(Math.max(...timestamps));

      let readingToStore;
      if (readings.length >= 2) {
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        readingToStore = {
          plotId,
          sensorId: `AVG_${readings.length}_sensors`,
          sensorType: 'moisture',
          value: avg,
          units: '%',
          timestamp: maxTs,
          contributingSensorIds: readings.map((r) => r.sensorId)
        };
      } else {
        const only = readings[0];
        readingToStore = {
          plotId,
          sensorId: only.sensorId,
          sensorType: 'moisture',
          value: only.value,
          units: '%',
          timestamp: only.timestamp,
          contributingSensorIds: null
        };
      }

      // Clean up stale rows for sensors moved from other plots
      for (const sid of uniqueIds) {
        try {
          await this.timescaleRepo.deleteStaleReadingsForSensor(this.repo.pool, {
            sensorId: sid,
            sensorType: 'moisture',
            currentPlotId: plotId
          });
        } catch (e) {
          this.logger.warn({ error: e, sensorId: sid, plotId }, 'Failed to delete stale readings');
        }
      }

      // Upsert the plot reading snapshot
      await this.timescaleRepo.upsertSensorPlotReading(this.repo.pool, readingToStore);
    }
  }
}

module.exports = { MoistureShapeIngest };
