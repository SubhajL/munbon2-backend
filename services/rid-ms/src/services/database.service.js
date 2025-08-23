"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DatabaseService = void 0;
const pg_1 = require("pg");
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class DatabaseService {
    static instance;
    pool;
    constructor() {
        this.pool = new pg_1.Pool({
            host: config_1.config.database.host,
            port: config_1.config.database.port,
            database: config_1.config.database.database,
            user: config_1.config.database.user,
            password: config_1.config.database.password,
            max: config_1.config.database.maxConnections,
            idleTimeoutMillis: config_1.config.database.idleTimeoutMillis,
        });
        this.pool.on('error', (err) => {
            logger_1.logger.error('Unexpected database error:', err);
        });
    }
    static getInstance() {
        if (!DatabaseService.instance) {
            DatabaseService.instance = new DatabaseService();
        }
        return DatabaseService.instance;
    }
    async initialize() {
        const client = await this.pool.connect();
        try {
            await client.query('BEGIN');
            await client.query('CREATE EXTENSION IF NOT EXISTS postgis');
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
            await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_shapefile_id ON parcels(shapefile_id)');
            await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_parcel_id ON parcels(parcel_id)');
            await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_zone ON parcels(zone)');
            await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_crop_type ON parcels(crop_type)');
            await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_water_demand_method ON parcels(water_demand_method)');
            await client.query('CREATE INDEX IF NOT EXISTS idx_parcels_geometry ON parcels USING GIST(geometry)');
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
            logger_1.logger.info('Database initialized successfully');
        }
        catch (error) {
            await client.query('ROLLBACK');
            logger_1.logger.error('Database initialization failed:', error);
            throw error;
        }
        finally {
            client.release();
        }
    }
    async saveShapeFileMetadata(metadata) {
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
    async updateShapeFileMetadata(metadata) {
        const updates = [];
        const values = [];
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
    async saveParcels(parcels) {
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
        }
        catch (error) {
            await client.query('ROLLBACK');
            throw error;
        }
        finally {
            client.release();
        }
    }
    async getParcelsByIds(parcelIds) {
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
    async getParcelsByZone(zone) {
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
    async getAllParcels() {
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
    async updateParcel(parcel) {
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
        if (parcel.waterDemand) {
            await this.saveWaterDemandHistory(parcel);
        }
    }
    async saveWaterDemandHistory(parcel) {
        const query = `
      INSERT INTO water_demand_history (
        id, parcel_id, calculation_date, method, daily_demand,
        weekly_demand, monthly_demand, seasonal_demand, parameters
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    `;
        const values = [
            (0, uuid_1.v4)(),
            parcel.id,
            parcel.waterDemand.lastCalculated,
            parcel.waterDemand.method,
            parcel.waterDemand.dailyDemand,
            parcel.waterDemand.weeklyDemand,
            parcel.waterDemand.monthlyDemand,
            parcel.waterDemand.seasonalDemand,
            JSON.stringify(parcel.waterDemand.parameters),
        ];
        await this.pool.query(query, values);
    }
    mapRowToParcel(row) {
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
    async close() {
        await this.pool.end();
    }
}
exports.DatabaseService = DatabaseService;
const uuid_1 = require("uuid");
//# sourceMappingURL=database.service.js.map