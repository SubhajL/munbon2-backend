"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ParcelsController = void 0;
const express_validator_1 = require("express-validator");
const pg_1 = require("pg");
const logger_1 = require("../utils/logger");
class ParcelsController {
    db;
    constructor() {
        this.db = new pg_1.Pool({
            connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres123@localhost:5435/rid_ms',
        });
    }
    async listParcels(req, res) {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { zone, cropType, ownerName, waterDemandMethod, limit = 50, offset = 0, sortBy = 'parcel_id', sortOrder = 'asc', } = req.query;
        try {
            let query = `
        SELECT 
          id,
          parcel_id,
          zone,
          sub_zone,
          area_rai,
          area_sqm,
          crop_type,
          owner_name,
          water_demand_method,
          ST_AsGeoJSON(centroid) as centroid,
          created_at,
          updated_at
        FROM parcels
        WHERE valid_to IS NULL
      `;
            const params = [];
            let paramCount = 0;
            if (zone) {
                paramCount++;
                query += ` AND zone = $${paramCount}`;
                params.push(zone);
            }
            if (cropType) {
                paramCount++;
                query += ` AND crop_type = $${paramCount}`;
                params.push(cropType);
            }
            if (ownerName) {
                paramCount++;
                query += ` AND owner_name ILIKE $${paramCount}`;
                params.push(`%${ownerName}%`);
            }
            if (waterDemandMethod) {
                paramCount++;
                query += ` AND water_demand_method = $${paramCount}`;
                params.push(waterDemandMethod);
            }
            const allowedSortFields = ['parcel_id', 'zone', 'area_rai', 'created_at'];
            const sortField = allowedSortFields.includes(sortBy) ? sortBy : 'parcel_id';
            const order = sortOrder === 'desc' ? 'DESC' : 'ASC';
            query += ` ORDER BY ${sortField} ${order}`;
            paramCount++;
            query += ` LIMIT $${paramCount}`;
            params.push(limit);
            paramCount++;
            query += ` OFFSET $${paramCount}`;
            params.push(offset);
            let countQuery = `
        SELECT COUNT(*) as total
        FROM parcels
        WHERE valid_to IS NULL
      `;
            const countParams = [];
            let countParamCount = 0;
            if (zone) {
                countParamCount++;
                countQuery += ` AND zone = $${countParamCount}`;
                countParams.push(zone);
            }
            if (cropType) {
                countParamCount++;
                countQuery += ` AND crop_type = $${countParamCount}`;
                countParams.push(cropType);
            }
            if (ownerName) {
                countParamCount++;
                countQuery += ` AND owner_name ILIKE $${countParamCount}`;
                countParams.push(`%${ownerName}%`);
            }
            if (waterDemandMethod) {
                countParamCount++;
                countQuery += ` AND water_demand_method = $${countParamCount}`;
                countParams.push(waterDemandMethod);
            }
            const [parcelsResult, countResult] = await Promise.all([
                this.db.query(query, params),
                this.db.query(countQuery, countParams),
            ]);
            const parcels = parcelsResult.rows.map(row => ({
                ...row,
                centroid: JSON.parse(row.centroid),
            }));
            res.json({
                parcels,
                pagination: {
                    total: parseInt(countResult.rows[0].total),
                    limit,
                    offset,
                    pages: Math.ceil(parseInt(countResult.rows[0].total) / limit),
                },
            });
        }
        catch (error) {
            logger_1.logger.error('Error listing parcels:', error);
            res.status(500).json({ error: 'Failed to list parcels' });
        }
    }
    async searchParcels(req, res) {
        const { q, searchFields = 'parcel_id,owner_name', limit = 50 } = req.query;
        try {
            const fields = searchFields.split(',').map(f => f.trim());
            const allowedFields = ['parcel_id', 'owner_name', 'owner_id', 'zone'];
            const validFields = fields.filter(f => allowedFields.includes(f));
            if (validFields.length === 0) {
                return res.status(400).json({ error: 'No valid search fields specified' });
            }
            const searchConditions = validFields.map((field, index) => `${field} ILIKE $${index + 2}`).join(' OR ');
            const query = `
        SELECT 
          id,
          parcel_id,
          zone,
          area_rai,
          crop_type,
          owner_name,
          water_demand_method,
          ST_AsGeoJSON(centroid) as centroid
        FROM parcels
        WHERE valid_to IS NULL
        AND (${searchConditions})
        LIMIT $1
      `;
            const params = [limit];
            validFields.forEach(() => params.push(`%${q}%`));
            const result = await this.db.query(query, params);
            const parcels = result.rows.map(row => ({
                ...row,
                centroid: JSON.parse(row.centroid),
            }));
            res.json({ parcels, count: parcels.length });
        }
        catch (error) {
            logger_1.logger.error('Error searching parcels:', error);
            res.status(500).json({ error: 'Failed to search parcels' });
        }
    }
    async getParcelById(req, res) {
        const { id } = req.params;
        try {
            const query = `
        SELECT 
          p.*,
          ST_AsGeoJSON(p.geometry) as geometry_geojson,
          ST_AsGeoJSON(p.centroid) as centroid_geojson,
          sfu.file_name as shape_file_name,
          sfu.upload_date
        FROM parcels p
        LEFT JOIN shape_file_uploads sfu ON p.shape_file_id = sfu.id
        WHERE p.id = $1 AND p.valid_to IS NULL
      `;
            const result = await this.db.query(query, [id]);
            if (result.rows.length === 0) {
                return res.status(404).json({ error: 'Parcel not found' });
            }
            const parcel = result.rows[0];
            parcel.geometry = JSON.parse(parcel.geometry_geojson);
            parcel.centroid = JSON.parse(parcel.centroid_geojson);
            delete parcel.geometry_geojson;
            delete parcel.centroid_geojson;
            const waterDemandQuery = `
        SELECT 
          calculated_date,
          method,
          daily_demand_cubic_meters,
          weekly_demand_cubic_meters,
          monthly_demand_cubic_meters,
          crop_coefficient,
          reference_et
        FROM water_demand_calculations
        WHERE parcel_id = $1
        ORDER BY calculated_date DESC
        LIMIT 1
      `;
            const waterDemandResult = await this.db.query(waterDemandQuery, [id]);
            if (waterDemandResult.rows.length > 0) {
                parcel.water_demand = waterDemandResult.rows[0];
            }
            res.json(parcel);
        }
        catch (error) {
            logger_1.logger.error('Error getting parcel:', error);
            res.status(500).json({ error: 'Failed to get parcel' });
        }
    }
    async getParcelHistory(req, res) {
        const { parcelId } = req.params;
        try {
            const query = `
        SELECT 
          id,
          parcel_id,
          valid_from,
          valid_to,
          zone,
          area_rai,
          crop_type,
          owner_name,
          water_demand_method,
          created_at
        FROM parcels
        WHERE parcel_id = $1
        ORDER BY valid_from DESC
      `;
            const result = await this.db.query(query, [parcelId]);
            res.json({
                parcelId,
                versions: result.rows,
                totalVersions: result.rows.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting parcel history:', error);
            res.status(500).json({ error: 'Failed to get parcel history' });
        }
    }
    async getParcelsAtDate(req, res) {
        const { date, zone, limit = 100, offset = 0 } = req.query;
        try {
            let query = `
        SELECT 
          id,
          parcel_id,
          zone,
          area_rai,
          crop_type,
          owner_name,
          water_demand_method,
          ST_AsGeoJSON(centroid) as centroid
        FROM parcels
        WHERE valid_from <= $1
        AND (valid_to IS NULL OR valid_to > $1)
      `;
            const params = [date];
            let paramCount = 1;
            if (zone) {
                paramCount++;
                query += ` AND zone = $${paramCount}`;
                params.push(zone);
            }
            paramCount++;
            query += ` LIMIT $${paramCount}`;
            params.push(limit);
            paramCount++;
            query += ` OFFSET $${paramCount}`;
            params.push(offset);
            const result = await this.db.query(query, params);
            const parcels = result.rows.map(row => ({
                ...row,
                centroid: JSON.parse(row.centroid),
            }));
            res.json({
                date,
                parcels,
                count: parcels.length,
            });
        }
        catch (error) {
            logger_1.logger.error('Error getting parcels at date:', error);
            res.status(500).json({ error: 'Failed to get parcels at date' });
        }
    }
    async updateParcel(req, res) {
        const { id } = req.params;
        const updates = req.body;
        const client = await this.db.connect();
        try {
            await client.query('BEGIN');
            const currentResult = await client.query('SELECT * FROM parcels WHERE id = $1 AND valid_to IS NULL', [id]);
            if (currentResult.rows.length === 0) {
                await client.query('ROLLBACK');
                return res.status(404).json({ error: 'Parcel not found' });
            }
            const current = currentResult.rows[0];
            const allowedFields = ['crop_type', 'water_demand_method', 'owner_name', 'planting_date', 'harvest_date'];
            const updateFields = [];
            const updateValues = [];
            let paramCount = 1;
            Object.keys(updates).forEach(key => {
                if (allowedFields.includes(key) && updates[key] !== undefined) {
                    updateFields.push(`${key} = $${paramCount}`);
                    updateValues.push(updates[key]);
                    paramCount++;
                }
            });
            if (updateFields.length === 0) {
                await client.query('ROLLBACK');
                return res.status(400).json({ error: 'No valid fields to update' });
            }
            updateFields.push(`updated_at = NOW()`);
            updateValues.push(id);
            const updateQuery = `
        UPDATE parcels 
        SET ${updateFields.join(', ')}
        WHERE id = $${paramCount} AND valid_to IS NULL
        RETURNING *
      `;
            const updateResult = await client.query(updateQuery, updateValues);
            await client.query('COMMIT');
            res.json({
                message: 'Parcel updated successfully',
                parcel: updateResult.rows[0],
            });
        }
        catch (error) {
            await client.query('ROLLBACK');
            logger_1.logger.error('Error updating parcel:', error);
            res.status(500).json({ error: 'Failed to update parcel' });
        }
        finally {
            client.release();
        }
    }
}
exports.ParcelsController = ParcelsController;
//# sourceMappingURL=parcels.controller.js.map