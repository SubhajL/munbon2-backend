import { Pool, PoolClient } from 'pg';
import { config } from '../config';
import { logger } from '../utils/logger';
import { ShapeFileMetadata, ParcelData, BoundingBox } from '../types';

export class DatabaseService {
  private static instance: DatabaseService;
  private pool: Pool;

  private constructor() {
    this.pool = new Pool({
      host: config.database.host,
      port: config.database.port,
      database: config.database.database,
      user: config.database.user,
      password: config.database.password,
      max: config.database.maxConnections,
      idleTimeoutMillis: config.database.idleTimeoutMillis,
    });

    this.pool.on('error', (err) => {
      logger.error('Unexpected database error:', err);
    });
  }

  public static getInstance(): DatabaseService {
    if (!DatabaseService.instance) {
      DatabaseService.instance = new DatabaseService();
    }
    return DatabaseService.instance;
  }

  /**
   * Initialize database tables
   */
  public async initialize(): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      // Create PostGIS extension if not exists
      await client.query('CREATE EXTENSION IF NOT EXISTS postgis');

      // Create shape file metadata table
      await client.query(`
        CREATE TABLE IF NOT EXISTS shapefile_metadata (
          id UUID PRIMARY KEY,
          original_file_name VARCHAR(255) NOT NULL,
          upload_date TIMESTAMP NOT NULL,
          processed_date TIMESTAMP,
          status VARCHAR(20) NOT NULL,
          error TEXT,
          file_size BIGINT NOT NULL,
          feature_count INTEGER,
          bounding_box GEOMETRY(POLYGON, 4326),
          coordinate_system VARCHAR(50) NOT NULL,
          attributes JSONB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
      `);

      // Create parcels table
      await client.query(`
        CREATE TABLE IF NOT EXISTS parcels (
          id UUID PRIMARY KEY,
          shapefile_id UUID REFERENCES shapefile_metadata(id) ON DELETE CASCADE,
          parcel_id VARCHAR(255) NOT NULL,
          geometry GEOMETRY(GEOMETRY, 4326) NOT NULL,
          area DECIMAL(15, 2) NOT NULL,
          zone VARCHAR(50),
          sub_zone VARCHAR(50),
          land_use_type VARCHAR(100),
          crop_type VARCHAR(100),
          planting_date DATE,
          harvest_date DATE,
          owner VARCHAR(255),
          water_demand_method VARCHAR(20) NOT NULL,
          water_demand JSONB,
          attributes JSONB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
      `);

      // Create indexes
      await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_shapefile_id ON parcels(shapefile_id)');
      await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_parcel_id ON parcels(parcel_id)');
      await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_zone ON parcels(zone)');
      await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_crop_type ON parcels(crop_type)');
      await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_water_demand_method ON parcels(water_demand_method)');
      await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_geometry ON parcels USING GIST(geometry)');

      // Create water demand history table
      await client.query(`
        CREATE TABLE IF NOT EXISTS water_demand_history (
          id UUID PRIMARY KEY,
          parcel_id UUID REFERENCES parcels(id) ON DELETE CASCADE,
          calculation_date TIMESTAMP NOT NULL,
          method VARCHAR(20) NOT NULL,
          daily_demand DECIMAL(15, 2) NOT NULL,
          weekly_demand DECIMAL(15, 2) NOT NULL,
          monthly_demand DECIMAL(15, 2) NOT NULL,
          seasonal_demand DECIMAL(15, 2) NOT NULL,
          parameters JSONB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
      `);

      await client.query('COMMIT');
      logger.info('Database initialized successfully');
    } catch (error) {
      await client.query('ROLLBACK');
      logger.error('Database initialization failed:', error);
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Save shape file metadata
   */
  public async saveShapeFileMetadata(metadata: ShapeFileMetadata): Promise<void> {
    const query = `
      INSERT INTO shapefile_metadata (
        id, original_file_name, upload_date, processed_date, status,
        error, file_size, feature_count, coordinate_system, attributes
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    `;

    const values = [
      metadata.id,
      metadata.originalFileName,
      metadata.uploadDate,
      metadata.processedDate,
      metadata.status,
      metadata.error,
      metadata.fileSize,
      metadata.featureCount,
      metadata.coordinateSystem,
      metadata.attributes ? JSON.stringify(metadata.attributes) : null,
    ];

    await this.pool.query(query, values);
  }

  /**
   * Update shape file metadata
   */
  public async updateShapeFileMetadata(metadata: Partial<ShapeFileMetadata> & { id: string }): Promise<void> {
    const updates: string[] = [];
    const values: any[] = [];
    let paramIndex = 1;

    if (metadata.status !== undefined) {
      updates.push(`status = $${paramIndex++}`);
      values.push(metadata.status);
    }
    if (metadata.processedDate !== undefined) {
      updates.push(`processed_date = $${paramIndex++}`);
      values.push(metadata.processedDate);
    }
    if (metadata.error !== undefined) {
      updates.push(`error = $${paramIndex++}`);
      values.push(metadata.error);
    }
    if (metadata.featureCount !== undefined) {
      updates.push(`feature_count = $${paramIndex++}`);
      values.push(metadata.featureCount);
    }
    if (metadata.boundingBox !== undefined) {
      const bbox = metadata.boundingBox;
      const polygon = `POLYGON((${bbox.minX} ${bbox.minY}, ${bbox.maxX} ${bbox.minY}, ${bbox.maxX} ${bbox.maxY}, ${bbox.minX} ${bbox.maxY}, ${bbox.minX} ${bbox.minY}))`;
      updates.push(`bounding_box = ST_GeomFromText($${paramIndex++}, 4326)`);
      values.push(polygon);
    }

    updates.push(`updated_at = CURRENT_TIMESTAMP`);
    values.push(metadata.id);

    const query = `
      UPDATE shapefile_metadata 
      SET ${updates.join(', ')}
      WHERE id = $${paramIndex}
    `;

    await this.pool.query(query, values);
  }

  /**
   * Save parcels in batch
   */
  public async saveParcels(parcels: ParcelData[]): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      const query = `
        INSERT INTO parcels (
          id, shapefile_id, parcel_id, geometry, area, zone, sub_zone,
          land_use_type, crop_type, planting_date, harvest_date, owner,
          water_demand_method, water_demand, attributes
        ) VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
      `;

      for (const parcel of parcels) {
        const values = [
          parcel.id,
          parcel.shapeFileId,
          parcel.parcelId,
          JSON.stringify(parcel.geometry),
          parcel.area,
          parcel.zone,
          parcel.subZone,
          parcel.landUseType,
          parcel.cropType,
          parcel.plantingDate,
          parcel.harvestDate,
          parcel.owner,
          parcel.waterDemandMethod,
          parcel.waterDemand ? JSON.stringify(parcel.waterDemand) : null,
          JSON.stringify(parcel.attributes),
        ];

        await client.query(query, values);
      }

      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Get parcels by IDs
   */
  public async getParcelsByIds(parcelIds: string[]): Promise<ParcelData[]> {
    const query = `
      SELECT 
        id, parcel_id, ST_AsGeoJSON(geometry) as geometry, area, zone, sub_zone,
        land_use_type, crop_type, planting_date, harvest_date, owner,
        water_demand_method, water_demand, attributes
      FROM parcels
      WHERE parcel_id = ANY($1)
    `;

    const result = await this.pool.query(query, [parcelIds]);
    return result.rows.map(row => this.mapRowToParcel(row));
  }

  /**
   * Get parcels by zone
   */
  public async getParcelsByZone(zone: string): Promise<ParcelData[]> {
    const query = `
      SELECT 
        id, parcel_id, ST_AsGeoJSON(geometry) as geometry, area, zone, sub_zone,
        land_use_type, crop_type, planting_date, harvest_date, owner,
        water_demand_method, water_demand, attributes
      FROM parcels
      WHERE zone = $1
    `;

    const result = await this.pool.query(query, [zone]);
    return result.rows.map(row => this.mapRowToParcel(row));
  }

  /**
   * Get all parcels
   */
  public async getAllParcels(): Promise<ParcelData[]> {
    const query = `
      SELECT 
        id, parcel_id, ST_AsGeoJSON(geometry) as geometry, area, zone, sub_zone,
        land_use_type, crop_type, planting_date, harvest_date, owner,
        water_demand_method, water_demand, attributes
      FROM parcels
    `;

    const result = await this.pool.query(query);
    return result.rows.map(row => this.mapRowToParcel(row));
  }

  /**
   * Update parcel
   */
  public async updateParcel(parcel: ParcelData): Promise<void> {
    const query = `
      UPDATE parcels
      SET 
        water_demand_method = $2,
        water_demand = $3,
        updated_at = CURRENT_TIMESTAMP
      WHERE id = $1
    `;

    const values = [
      parcel.id,
      parcel.waterDemandMethod,
      JSON.stringify(parcel.waterDemand),
    ];

    await this.pool.query(query, values);

    // Save to history
    if (parcel.waterDemand) {
      await this.saveWaterDemandHistory(parcel);
    }
  }

  /**
   * Save water demand history
   */
  private async saveWaterDemandHistory(parcel: ParcelData): Promise<void> {
    const query = `
      INSERT INTO water_demand_history (
        id, parcel_id, calculation_date, method, daily_demand,
        weekly_demand, monthly_demand, seasonal_demand, parameters
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    `;

    const values = [
      uuidv4(),
      parcel.id,
      parcel.waterDemand!.lastCalculated,
      parcel.waterDemand!.method,
      parcel.waterDemand!.dailyDemand,
      parcel.waterDemand!.weeklyDemand,
      parcel.waterDemand!.monthlyDemand,
      parcel.waterDemand!.seasonalDemand,
      JSON.stringify(parcel.waterDemand!.parameters),
    ];

    await this.pool.query(query, values);
  }

  /**
   * Map database row to ParcelData
   */
  private mapRowToParcel(row: any): ParcelData {
    return {
      id: row.id,
      parcelId: row.parcel_id,
      geometry: JSON.parse(row.geometry),
      area: parseFloat(row.area),
      zone: row.zone,
      subZone: row.sub_zone,
      landUseType: row.land_use_type,
      cropType: row.crop_type,
      plantingDate: row.planting_date,
      harvestDate: row.harvest_date,
      owner: row.owner,
      waterDemandMethod: row.water_demand_method,
      waterDemand: row.water_demand,
      attributes: row.attributes,
    };
  }

  /**
   * Close database connection
   */
  public async close(): Promise<void> {
    await this.pool.end();
  }
}

// Import uuid for water demand history
import { v4 as uuidv4 } from 'uuid';