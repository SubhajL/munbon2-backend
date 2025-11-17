class WaterLevelLocationListener {
  constructor({ sensorDbPool, configDbPool, logger }) {
    this.sensorDb = sensorDbPool; // connects to sensor_data
    this.configDb = configDbPool; // connects to munbon_dev
    this.logger = logger || console;
    this.pollMs = 30000;
    this.recentLimit = parseInt(process.env.WL_RECENT_LIMIT || '10');
    this.timer = null;
  }

  async start() {
    if (process.env.WL_LISTEN === 'true') {
      await this.startListen();
      return;
    }
    await this.processOnce();
    this.timer = setInterval(
      () => this.processOnce().catch((e) => this.logger.error(e)),
      this.pollMs
    );
    this.logger.info('WaterLevelLocationListener started');
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
  }

  async processOnce() {
    // Select from only the most recent N rows overall (performance-friendly)
    const q = `
      WITH recent AS (
        SELECT sensor_id,
               COALESCE(location_lng, CAST(NULL AS DOUBLE PRECISION)) AS location_lng,
               COALESCE(location_lat, CAST(NULL AS DOUBLE PRECISION)) AS location_lat,
               time AS timestamp
        FROM public.water_level_readings
        WHERE location_lng IS NOT NULL AND location_lat IS NOT NULL
        ORDER BY time DESC
        LIMIT ${this.recentLimit}
      )
      SELECT DISTINCT ON (sensor_id)
        sensor_id AS device_id,
        location_lng AS lng,
        location_lat AS lat
      FROM recent
      ORDER BY sensor_id, timestamp DESC
    `;

    const { rows } = await this.sensorDb.query(q);
    for (const r of rows) {
      await this._upsertLocation({
        deviceId: r.device_id,
        lng: Number(r.lng),
        lat: Number(r.lat)
      });
    }
  }

  async startListen() {
    const { Client } = require('pg');
    this.listenClient = new Client({
      host: process.env.TIMESCALE_HOST,
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB || 'sensor_data',
      user: process.env.TIMESCALE_USER,
      password: process.env.TIMESCALE_PASSWORD
    });
    await this.listenClient.connect();
    await this.listenClient.query('LISTEN wl_location_changed');
    this.listenClient.on('notification', async (msg) => {
      try {
        await this._handleNotify(msg.payload);
      } catch (e) {
        this.logger.error('WL notify handler error', e);
      }
    });
    this.logger.info('Listening on channel wl_location_changed');
  }

  async _handleNotify(payload) {
    if (!payload) return;
    let data;
    try {
      data = typeof payload === 'string' ? JSON.parse(payload) : payload;
    } catch {
      return;
    }
    const { sensor_id, lng, lat } = data || {};
    if (!sensor_id || typeof lng !== 'number' || typeof lat !== 'number')
      return;
    await this._upsertLocation({ deviceId: sensor_id, lng, lat });
  }

  async _upsertLocation({ deviceId, lng, lat }) {
    const sql = `
      INSERT INTO ros_gis_smartfarm.sensor_locations
        (device_id, device_name, device_type, lng, lat, updated_at)
      VALUES ($1, $1, 'water_level_sensor', $2, $3, NOW())
      ON CONFLICT (device_id)
      DO UPDATE SET lng = EXCLUDED.lng, lat = EXCLUDED.lat, updated_at = NOW()
    `;
    await this.configDb.query(sql, [deviceId, lng, lat]);
  }
}

module.exports = { WaterLevelLocationListener };
