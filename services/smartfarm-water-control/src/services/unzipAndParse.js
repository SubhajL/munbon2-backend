const fs = require('fs');
const path = require('path');
const os = require('os');
const AdmZip = require('adm-zip');
const { MoistureShapeIngest } = require('./moistureShapeIngest');
const ConfigRepository = require('../repository/configRepository');
const { TimescaleRepository } = require('../repository/timescaleRepository');
const { Pool } = require('pg');

async function unzipAndParse(zipPath, logger = console) {
  if (!fs.existsSync(zipPath)) throw new Error('zip not found');
  const base = path.basename(zipPath);
  if (!/^\d{8}-moisturesensors\.zip$/i.test(base)) throw new Error('filename pattern mismatch');

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sf-zip-'));
  const zip = new AdmZip(zipPath);
  zip.extractAllTo(tempDir, true);

  const configPool = new Pool({
    host: process.env.CONFIG_DB_HOST || process.env.TIMESCALE_HOST,
    port: parseInt(process.env.CONFIG_DB_PORT || process.env.TIMESCALE_PORT || '5432'),
    database: process.env.CONFIG_DB_NAME || 'munbon_dev',
    user: process.env.CONFIG_DB_USER || process.env.TIMESCALE_USER,
    password: process.env.CONFIG_DB_PASSWORD || process.env.TIMESCALE_PASSWORD
  });
  const repo = new ConfigRepository({ configDbPool: configPool, pool: configPool, logger, schemas: { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' } });

  const timescalePool = new Pool({
    host: process.env.TIMESCALE_HOST,
    port: parseInt(process.env.TIMESCALE_PORT || '5432'),
    database: process.env.TIMESCALE_DB || 'sensor_data',
    user: process.env.TIMESCALE_USER,
    password: process.env.TIMESCALE_PASSWORD
  });
  const timescaleRepo = new TimescaleRepository(timescalePool, {
    planning: process.env.TIMESCALE_SCHEMA_PLANNING || 'ros_gis_smartfarm',
    control: process.env.TIMESCALE_SCHEMA_CONTROL || 'water_control_smartfarm'
  });

  const ingest = new MoistureShapeIngest({ repo, logger, timescaleRepo });

  const count = await ingest._importFromDir(tempDir);
  await configPool.end();
  await timescalePool.end();
  return { count, tempDir };
}

module.exports = { unzipAndParse };