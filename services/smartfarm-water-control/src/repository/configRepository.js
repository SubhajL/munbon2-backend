const ALLOWED_DEVICE_TYPES = new Set(['solenoid_valve', 'flow_meter', 'moisture_sensor', 'water_level_sensor', 'valve']);
const ALLOWED_CONTROL_MODES = new Set(['AWD', 'MOISTURE', 'none']);

class ConfigRepository {
  constructor({ pool, logger, schemas }) {
    this.pool = pool;
    this.logger = logger || console;
    this.schemas = schemas || { smartfarm: 'ros_gis_smartfarm', control: 'water_control_smartfarm' };
  }

  // ros_gis_smartfarm.plot_boundaries
  async upsertPlotBoundary({ plotId, plotName, areaRai, geojson }) {
    if (!plotId || !geojson) throw new Error('plotId and geojson are required');
    if (!Array.isArray(geojson.coordinates) || geojson.type !== 'Polygon') {
      throw new Error('geojson must be a Polygon');
    }
    if (!(areaRai > 0)) throw new Error('areaRai must be > 0');

    const sql = `
      INSERT INTO ${this.schemas.smartfarm}.plot_boundaries
        (plot_id, plot_name, area_rai, geom, updated_at)
      VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), NOW())
      ON CONFLICT (plot_id)
      DO UPDATE SET
        plot_name = EXCLUDED.plot_name,
        area_rai = EXCLUDED.area_rai,
        geom = EXCLUDED.geom,
        updated_at = NOW()
    `;
    const params = [plotId, plotName || null, areaRai, JSON.stringify(geojson)];
    await this.pool.query(sql, params);
  }

  // ros_gis_smartfarm.device_inventory
  async upsertDevice({ deviceName, deviceType, zone, metadata }) {
    if (!deviceName || !deviceType) throw new Error('deviceName and deviceType are required');
    if (!ALLOWED_DEVICE_TYPES.has(deviceType)) throw new Error(`deviceType not allowed: ${deviceType}`);

    const sql = `
      INSERT INTO ${this.schemas.smartfarm}.device_inventory
        (device_name, device_type, zone, metadata, updated_at)
      VALUES ($1, $2, $3, $4::jsonb, NOW())
      ON CONFLICT (device_name, device_type)
      DO UPDATE SET
        zone = EXCLUDED.zone,
        metadata = EXCLUDED.metadata,
        updated_at = NOW()
    `;
    await this.pool.query(sql, [deviceName, deviceType, zone || null, JSON.stringify(metadata || {})]);
  }

  // ros_gis_smartfarm.sensor_locations
  async upsertSensorLocation({ deviceId, deviceName, deviceType, lng, lat, plotId }) {
    if (!deviceId || !deviceName || !deviceType) throw new Error('deviceId, deviceName, deviceType are required');
    if (!ALLOWED_DEVICE_TYPES.has(deviceType)) throw new Error(`deviceType not allowed: ${deviceType}`);
    if (typeof lng !== 'number' || typeof lat !== 'number') throw new Error('lng/lat must be numbers');

    const sql = `
      INSERT INTO ${this.schemas.smartfarm}.sensor_locations
        (device_id, device_name, device_type, lng, lat, plot_id, updated_at)
      VALUES ($1, $2, $3, $4, $5, $6, NOW())
      ON CONFLICT (device_id)
      DO UPDATE SET
        device_name = EXCLUDED.device_name,
        device_type = EXCLUDED.device_type,
        lng = EXCLUDED.lng,
        lat = EXCLUDED.lat,
        plot_id = EXCLUDED.plot_id,
        updated_at = NOW()
    `;
    await this.pool.query(sql, [deviceId, deviceName, deviceType, lng, lat, plotId || null]);
  }

  // water_control_smartfarm.plot_configurations
  async upsertPlotConfiguration({ plotId, cropType, controlMode }) {
    if (!plotId) throw new Error('plotId is required');
    if (controlMode && !ALLOWED_CONTROL_MODES.has(controlMode)) {
      throw new Error(`controlMode not allowed: ${controlMode}`);
    }
    const sql = `
      INSERT INTO ${this.schemas.control}.plot_configurations
        (plot_id, crop_type, control_mode, updated_at)
      VALUES ($1, $2, $3, NOW())
      ON CONFLICT (plot_id)
      DO UPDATE SET
        crop_type = EXCLUDED.crop_type,
        control_mode = EXCLUDED.control_mode,
        updated_at = NOW()
    `;
    await this.pool.query(sql, [plotId, cropType || null, controlMode || null]);
  }

  // water_control_smartfarm.sensor_plot_mapping (unique on sensor_id)
  async upsertSensorMapping({ sensorId, plotId, sensorType }) {
    if (!sensorId || !plotId || !sensorType) throw new Error('sensorId, plotId, sensorType required');
    const allowed = new Set(['moisture', 'water_level', 'valve']);
    if (!allowed.has(sensorType)) throw new Error(`sensorType not allowed: ${sensorType}`);

    const sql = `
      INSERT INTO ${this.schemas.control}.sensor_plot_mapping
        (sensor_id, plot_id, sensor_type, updated_at)
      VALUES ($1, $2, $3, NOW())
      ON CONFLICT (sensor_id)
      DO UPDATE SET
        plot_id = EXCLUDED.plot_id,
        sensor_type = EXCLUDED.sensor_type,
        updated_at = NOW()
    `;
    await this.pool.query(sql, [sensorId, plotId, sensorType]);
  }
}

module.exports = ConfigRepository;