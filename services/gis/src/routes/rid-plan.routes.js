"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const database_1 = require("../config/database");
const logger_1 = require("../utils/logger");
const auth_1 = require("../middleware/auth");
const async_handler_1 = require("../middleware/async-handler");
const router = (0, express_1.Router)();
router.get('/parcels', auth_1.authenticateJWT, [
    (0, express_validator_1.query)('amphoe').optional().isString(),
    (0, express_validator_1.query)('tambon').optional().isString(),
    (0, express_validator_1.query)('plantId').optional().isString(),
    (0, express_validator_1.query)('minArea').optional().isFloat({ min: 0 }),
    (0, express_validator_1.query)('maxArea').optional().isFloat({ min: 0 }),
    (0, express_validator_1.query)('page').optional().isInt({ min: 1 }).default(1),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 100 }).default(20),
    (0, express_validator_1.query)('bbox').optional().matches(/^-?\d+\.?\d*,-?\d+\.?\d*,-?\d+\.?\d*,-?\d+\.?\d*$/),
], (0, async_handler_1.asyncHandler)(async (req, res) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    const { amphoe, tambon, plantId, minArea, maxArea, page = 1, limit = 20, bbox } = req.query;
    const offset = (Number(page) - 1) * Number(limit);
    try {
        let query = `
        SELECT 
          id,
          plot_code,
          area_hectares,
          ST_AsGeoJSON(boundary) as geometry,
          current_crop_type,
          properties,
          created_at,
          updated_at
        FROM gis.agricultural_plots
        WHERE 1=1
      `;
        const params = [];
        let paramCount = 0;
        if (amphoe) {
            paramCount++;
            query += ` AND properties->>'location'->>'amphoe' = $${paramCount}`;
            params.push(amphoe);
        }
        if (tambon) {
            paramCount++;
            query += ` AND properties->>'location'->>'tambon' = $${paramCount}`;
            params.push(tambon);
        }
        if (plantId) {
            paramCount++;
            query += ` AND (properties->'ridAttributes'->>'plantId' = $${paramCount} OR current_crop_type = $${paramCount})`;
            params.push(plantId);
        }
        if (minArea) {
            paramCount++;
            query += ` AND area_hectares >= $${paramCount}`;
            params.push(Number(minArea));
        }
        if (maxArea) {
            paramCount++;
            query += ` AND area_hectares <= $${paramCount}`;
            params.push(Number(maxArea));
        }
        if (bbox) {
            const [minLon, minLat, maxLon, maxLat] = bbox.split(',').map(Number);
            paramCount++;
            query += ` AND ST_Intersects(boundary, ST_MakeEnvelope($${paramCount}, $${paramCount + 1}, $${paramCount + 2}, $${paramCount + 3}, 4326))`;
            params.push(minLon, minLat, maxLon, maxLat);
            paramCount += 3;
        }
        query += ` AND properties->>'uploadId' LIKE 'ridplan-%'`;
        const countQuery = `SELECT COUNT(*) as total FROM (${query}) as subquery`;
        const countResult = await database_1.AppDataSource.query(countQuery, params);
        const total = parseInt(countResult[0].total);
        paramCount++;
        query += ` ORDER BY created_at DESC LIMIT $${paramCount}`;
        params.push(Number(limit));
        paramCount++;
        query += ` OFFSET $${paramCount}`;
        params.push(offset);
        const parcels = await database_1.AppDataSource.query(query, params);
        const features = parcels.map((parcel) => ({
            type: 'Feature',
            properties: {
                id: parcel.id,
                plotCode: parcel.plot_code,
                areaHectares: parcel.area_hectares,
                areaRai: parcel.area_hectares * 6.25,
                cropType: parcel.current_crop_type,
                ...parcel.properties.ridAttributes,
                amphoe: parcel.properties.location?.amphoe,
                tambon: parcel.properties.location?.tambon,
                lastUpdated: parcel.updated_at || parcel.created_at
            },
            geometry: JSON.parse(parcel.geometry)
        }));
        res.json({
            type: 'FeatureCollection',
            features,
            pagination: {
                page: Number(page),
                limit: Number(limit),
                total,
                totalPages: Math.ceil(total / Number(limit))
            }
        });
    }
    catch (error) {
        logger_1.logger.error('Error fetching RID Plan parcels', { error });
        res.status(500).json({
            error: 'Failed to fetch parcels',
            message: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}));
router.get('/parcels/:id', auth_1.authenticateJWT, (0, async_handler_1.asyncHandler)(async (req, res) => {
    const { id } = req.params;
    try {
        const result = await database_1.AppDataSource.query(`
        SELECT 
          id,
          plot_code,
          farmer_id,
          zone_id,
          area_hectares,
          ST_AsGeoJSON(boundary) as geometry,
          current_crop_type,
          soil_type,
          properties,
          created_at,
          updated_at
        FROM gis.agricultural_plots
        WHERE id = $1 AND properties->>'uploadId' LIKE 'ridplan-%'
      `, [id]);
        if (result.length === 0) {
            return res.status(404).json({ error: 'Parcel not found' });
        }
        const parcel = result[0];
        res.json({
            type: 'Feature',
            properties: {
                id: parcel.id,
                plotCode: parcel.plot_code,
                farmerId: parcel.farmer_id,
                zoneId: parcel.zone_id,
                areaHectares: parcel.area_hectares,
                areaRai: parcel.area_hectares * 6.25,
                cropType: parcel.current_crop_type,
                soilType: parcel.soil_type,
                ...parcel.properties,
                createdAt: parcel.created_at,
                updatedAt: parcel.updated_at
            },
            geometry: JSON.parse(parcel.geometry)
        });
    }
    catch (error) {
        logger_1.logger.error('Error fetching parcel', { error, id });
        res.status(500).json({
            error: 'Failed to fetch parcel',
            message: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}));
router.get('/statistics', auth_1.authenticateJWT, [
    (0, express_validator_1.query)('groupBy').optional().isIn(['amphoe', 'tambon', 'cropType', 'zone']),
    (0, express_validator_1.query)('amphoe').optional().isString(),
    (0, express_validator_1.query)('tambon').optional().isString(),
], (0, async_handler_1.asyncHandler)(async (req, res) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    const { groupBy = 'amphoe', amphoe, tambon } = req.query;
    try {
        let groupColumn;
        let groupExpression;
        switch (groupBy) {
            case 'amphoe':
                groupExpression = "properties->'location'->>'amphoe'";
                groupColumn = 'amphoe';
                break;
            case 'tambon':
                groupExpression = "properties->'location'->>'tambon'";
                groupColumn = 'tambon';
                break;
            case 'cropType':
                groupExpression = 'current_crop_type';
                groupColumn = 'crop_type';
                break;
            case 'zone':
                groupExpression = 'zone_id';
                groupColumn = 'zone_id';
                break;
            default:
                groupExpression = "properties->'location'->>'amphoe'";
                groupColumn = 'amphoe';
        }
        let query = `
        SELECT 
          ${groupExpression} as ${groupColumn},
          COUNT(*) as parcel_count,
          SUM(area_hectares) as total_area_hectares,
          SUM(area_hectares * 6.25) as total_area_rai,
          AVG(area_hectares * 6.25) as avg_area_rai,
          MIN(area_hectares * 6.25) as min_area_rai,
          MAX(area_hectares * 6.25) as max_area_rai,
          SUM(CAST(properties->'ridAttributes'->>'yieldAtMcKgpr' AS FLOAT)) as total_yield_kg,
          AVG(CAST(properties->'ridAttributes'->>'yieldAtMcKgpr' AS FLOAT)) as avg_yield_kg_per_rai,
          SUM(CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) * area_hectares * 6.25) as total_water_usage_m3,
          AVG(CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT)) as avg_water_usage_m3_per_rai
        FROM gis.agricultural_plots
        WHERE properties->>'uploadId' LIKE 'ridplan-%'
      `;
        const params = [];
        let paramCount = 0;
        if (amphoe) {
            paramCount++;
            query += ` AND properties->'location'->>'amphoe' = $${paramCount}`;
            params.push(amphoe);
        }
        if (tambon) {
            paramCount++;
            query += ` AND properties->'location'->>'tambon' = $${paramCount}`;
            params.push(tambon);
        }
        query += ` GROUP BY ${groupExpression} ORDER BY total_area_hectares DESC`;
        const stats = await database_1.AppDataSource.query(query, params);
        const summaryQuery = `
        SELECT 
          COUNT(*) as total_parcels,
          SUM(area_hectares) as total_area_hectares,
          SUM(area_hectares * 6.25) as total_area_rai,
          AVG(area_hectares * 6.25) as avg_area_rai,
          COUNT(DISTINCT properties->'location'->>'amphoe') as unique_amphoe,
          COUNT(DISTINCT properties->'location'->>'tambon') as unique_tambon
        FROM gis.agricultural_plots
        WHERE properties->>'uploadId' LIKE 'ridplan-%'
      `;
        const summary = await database_1.AppDataSource.query(summaryQuery);
        res.json({
            summary: summary[0],
            statistics: stats,
            groupedBy: groupBy
        });
    }
    catch (error) {
        logger_1.logger.error('Error fetching statistics', { error });
        res.status(500).json({
            error: 'Failed to fetch statistics',
            message: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}));
router.get('/search', auth_1.authenticateJWT, [
    (0, express_validator_1.query)('q').notEmpty().isString().trim(),
    (0, express_validator_1.query)('type').optional().isIn(['amphoe', 'tambon', 'both']).default('both'),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 50 }).default(10),
], (0, async_handler_1.asyncHandler)(async (req, res) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    const { q, type = 'both', limit = 10 } = req.query;
    try {
        let results = [];
        if (type === 'amphoe' || type === 'both') {
            const amphoeQuery = `
          SELECT DISTINCT 
            properties->'location'->>'amphoe' as name,
            'amphoe' as type,
            COUNT(*) as parcel_count,
            SUM(area_hectares * 6.25) as total_area_rai
          FROM gis.agricultural_plots
          WHERE properties->>'uploadId' LIKE 'ridplan-%'
            AND properties->'location'->>'amphoe' ILIKE $1
          GROUP BY properties->'location'->>'amphoe'
          LIMIT $2
        `;
            const amphoeResults = await database_1.AppDataSource.query(amphoeQuery, [`%${q}%`, limit]);
            results = results.concat(amphoeResults.map((r) => ({ ...r, type: 'amphoe' })));
        }
        if (type === 'tambon' || type === 'both') {
            const tambonQuery = `
          SELECT DISTINCT 
            properties->'location'->>'tambon' as name,
            properties->'location'->>'amphoe' as amphoe,
            'tambon' as type,
            COUNT(*) as parcel_count,
            SUM(area_hectares * 6.25) as total_area_rai
          FROM gis.agricultural_plots
          WHERE properties->>'uploadId' LIKE 'ridplan-%'
            AND properties->'location'->>'tambon' ILIKE $1
          GROUP BY properties->'location'->>'tambon', properties->'location'->>'amphoe'
          LIMIT $2
        `;
            const tambonResults = await database_1.AppDataSource.query(tambonQuery, [`%${q}%`, limit]);
            results = results.concat(tambonResults.map((r) => ({ ...r, type: 'tambon' })));
        }
        res.json({
            query: q,
            results: results.slice(0, Number(limit))
        });
    }
    catch (error) {
        logger_1.logger.error('Error searching locations', { error });
        res.status(500).json({
            error: 'Failed to search locations',
            message: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}));
router.get('/water-demand', auth_1.authenticateJWT, [
    (0, express_validator_1.query)('amphoe').optional().isString(),
    (0, express_validator_1.query)('tambon').optional().isString(),
    (0, express_validator_1.query)('month').optional().isInt({ min: 1, max: 12 }),
], (0, async_handler_1.asyncHandler)(async (req, res) => {
    const errors = (0, express_validator_1.validationResult)(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }
    const { amphoe, tambon, month } = req.query;
    try {
        let query = `
        SELECT 
          properties->'location'->>'amphoe' as amphoe,
          properties->'location'->>'tambon' as tambon,
          COUNT(*) as parcel_count,
          SUM(area_hectares * 6.25) as total_area_rai,
          SUM(
            CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) * 
            area_hectares * 6.25
          ) as total_seasonal_water_m3,
          AVG(CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT)) as avg_water_per_rai,
          SUM(CAST(properties->'ridAttributes'->>'wpet' AS FLOAT)) as total_water_pet,
          AVG(CAST(properties->'ridAttributes'->>'wpet' AS FLOAT)) as avg_water_pet
        FROM gis.agricultural_plots
        WHERE properties->>'uploadId' LIKE 'ridplan-%'
      `;
        const params = [];
        let paramCount = 0;
        if (amphoe) {
            paramCount++;
            query += ` AND properties->'location'->>'amphoe' = $${paramCount}`;
            params.push(amphoe);
        }
        if (tambon) {
            paramCount++;
            query += ` AND properties->'location'->>'tambon' = $${paramCount}`;
            params.push(tambon);
        }
        if (month) {
            query = query.replace('total_seasonal_water_m3', 'total_seasonal_water_m3 / 4 as monthly_water_m3');
        }
        query += ` GROUP BY properties->'location'->>'amphoe', properties->'location'->>'tambon'
                 ORDER BY total_seasonal_water_m3 DESC`;
        const waterDemand = await database_1.AppDataSource.query(query, params);
        const totalQuery = `
        SELECT 
          SUM(
            CAST(properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) * 
            area_hectares * 6.25
          ) as grand_total_water_m3,
          SUM(area_hectares * 6.25) as grand_total_area_rai
        FROM gis.agricultural_plots
        WHERE properties->>'uploadId' LIKE 'ridplan-%'
      `;
        const totals = await database_1.AppDataSource.query(totalQuery +
            (amphoe ? ` AND properties->'location'->>'amphoe' = $1` : '') +
            (tambon ? ` AND properties->'location'->>'tambon' = $${amphoe ? 2 : 1}` : ''), params);
        res.json({
            waterDemand,
            summary: {
                totalWaterDemandM3: totals[0].grand_total_water_m3,
                totalAreaRai: totals[0].grand_total_area_rai,
                waterDemandPerRai: totals[0].grand_total_water_m3 / totals[0].grand_total_area_rai,
                month: month ? Number(month) : null
            }
        });
    }
    catch (error) {
        logger_1.logger.error('Error calculating water demand', { error });
        res.status(500).json({
            error: 'Failed to calculate water demand',
            message: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}));
exports.default = router;
//# sourceMappingURL=rid-plan.routes.js.map