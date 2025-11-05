import { Pool, PoolConfig } from 'pg';

export type PlotThresholds = {
  moistureLower: number | null;
  moistureUpper: number | null;
  waterLevelLower: number | null;
  waterLevelUpper: number | null;
};

export interface SmartFarmRepositoryLike {
  getPlotMappingsBySensorIds(sensorIds: string[]): Promise<Record<string, string>>;
  getThresholdsByPlotIds(plotIds: string[]): Promise<Record<string, PlotThresholds>>;
}

export class SmartFarmRepository implements SmartFarmRepositoryLike {
  private pool: Pool;

  constructor(config?: PoolConfig) {
    const cfg: PoolConfig = config ?? {
      host: process.env.CONFIG_DB_HOST || process.env.DB_HOST || process.env.TIMESCALE_HOST || 'localhost',
      port: parseInt(process.env.CONFIG_DB_PORT || process.env.DB_PORT || process.env.TIMESCALE_PORT || '5432', 10),
      database: process.env.CONFIG_DB_NAME || 'munbon_dev',
      user: process.env.CONFIG_DB_USER || process.env.TIMESCALE_USER || 'postgres',
      password: process.env.CONFIG_DB_PASSWORD || process.env.TIMESCALE_PASSWORD || '',
    };
    this.pool = new Pool({ ...cfg, keepAlive: true });
    this.pool.on('error', (err) => {
      // eslint-disable-next-line no-console
      console.error('pg(config): unexpected pool error (ignored)', err?.message);
    });
  }

  async getPlotMappingsBySensorIds(sensorIds: string[]): Promise<Record<string, string>> {
    if (sensorIds.length === 0) return {};
    const schema = process.env.CONFIG_DB_SCHEMA || 'water_control_smartfarm';
    // Heuristic: some moisture IDs are in the form '0001-0001' but the mapping uses a
    // zero-padded numeric like '00000001'. For such IDs, try a normalized variant.
    const normalized: string[] = [];
    const backMap: Record<string, string> = {};
    for (const id of sensorIds) {
      const m = id.match(/^(\d{1,5})-(\d{1,5})$/);
      if (m) {
        const normalizedId = String(parseInt(m[2], 10)).padStart(8, '0');
        normalized.push(normalizedId);
        backMap[normalizedId] = id;
      }
    }

    const searchIds = Array.from(new Set([...sensorIds, ...normalized]));

    const result = await this.pool.query(
      `SELECT sensor_id, plot_id FROM ${schema}.v_sensor_plot_mapping_enriched WHERE sensor_id = ANY($1)`,
      [searchIds]
    );
    const map: Record<string, string> = {};
    for (const row of result.rows) {
      const original = backMap[row.sensor_id] || row.sensor_id;
      map[original] = row.plot_id;
    }
    return map;
  }

  async getThresholdsByPlotIds(plotIds: string[]): Promise<Record<string, PlotThresholds>> {
    if (plotIds.length === 0) return {};
    const schema = process.env.CONFIG_DB_SCHEMA || 'water_control_smartfarm';
    const result = await this.pool.query(
      `SELECT plot_id, moisture_lower_threshold, moisture_upper_threshold, water_level_lower_threshold, water_level_upper_threshold
       FROM ${schema}.control_thresholds
       WHERE plot_id = ANY($1)`,
      [plotIds]
    );
    const map: Record<string, PlotThresholds> = {};
    for (const row of result.rows) {
      map[row.plot_id] = {
        moistureLower: row.moisture_lower_threshold ?? null,
        moistureUpper: row.moisture_upper_threshold ?? null,
        waterLevelLower: row.water_level_lower_threshold ?? null,
        waterLevelUpper: row.water_level_upper_threshold ?? null,
      };
    }
    return map;
  }
}
