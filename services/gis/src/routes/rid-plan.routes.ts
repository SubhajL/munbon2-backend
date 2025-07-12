import { Router } from 'express';
import { query, validationResult } from 'express-validator';
import { AppDataSource } from '../config/database';
import { logger } from '../utils/logger';
import { authenticateJWT } from '../middleware/auth';
import { asyncHandler } from '../middleware/async-handler';

const router = Router();

// Get RID Plan parcels with filtering and pagination
router.get('/parcels',
  authenticateJWT,
  [
    query('amphoe').optional().isString(),
    query('tambon').optional().isString(),
    query('plantId').optional().isString(),
    query('minArea').optional().isFloat({ min: 0 }),
    query('maxArea').optional().isFloat({ min: 0 }),
    query('page').optional().isInt({ min: 1 }).default(1),
    query('limit').optional().isInt({ min: 1, max: 100 }).default(20),
    query('bbox').optional().matches(/^-?\d+\.?\d*,-?\d+\.?\d*,-?\d+\.?\d*,-?\d+\.?\d*$/),
  ],
  asyncHandler(async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const {
      amphoe,
      tambon,
      plantId,
      minArea,
      maxArea,
      page = 1,
      limit = 20,
      bbox
    } = req.query;

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

      const params: any[] = [];
      let paramCount = 0;

      // Filter by amphoe
      if (amphoe) {
        paramCount++;
        query += ` AND properties->>'location'->>'amphoe' = $${paramCount}`;
        params.push(amphoe);
      }

      // Filter by tambon
      if (tambon) {
        paramCount++;
        query += ` AND properties->>'location'->>'tambon' = $${paramCount}`;
        params.push(tambon);
      }

      // Filter by plant ID
      if (plantId) {
        paramCount++;
        query += ` AND (properties->'ridAttributes'->>'plantId' = $${paramCount} OR current_crop_type = $${paramCount})`;
        params.push(plantId);
      }

      // Filter by area range
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

      // Spatial filter by bounding box
      if (bbox) {
        const [minLon, minLat, maxLon, maxLat] = (bbox as string).split(',').map(Number);
        paramCount++;
        query += ` AND ST_Intersects(boundary, ST_MakeEnvelope($${paramCount}, $${paramCount + 1}, $${paramCount + 2}, $${paramCount + 3}, 4326))`;
        params.push(minLon, minLat, maxLon, maxLat);
        paramCount += 3;
      }

      // Filter by upload ID (RID Plan data)
      query += ` AND properties->>'uploadId' LIKE 'ridplan-%'`;

      // Get total count
      const countQuery = `SELECT COUNT(*) as total FROM (${query}) as subquery`;
      const countResult = await AppDataSource.query(countQuery, params);
      const total = parseInt(countResult[0].total);

      // Add pagination
      paramCount++;
      query += ` ORDER BY created_at DESC LIMIT $${paramCount}`;
      params.push(Number(limit));
      
      paramCount++;
      query += ` OFFSET $${paramCount}`;
      params.push(offset);

      // Execute query
      const parcels = await AppDataSource.query(query, params);

      // Format response
      const features = parcels.map((parcel: any) => ({
        type: 'Feature',
        properties: {
          id: parcel.id,
          plotCode: parcel.plot_code,
          areaHectares: parcel.area_hectares,
          areaRai: parcel.area_hectares * 6.25, // Convert to rai
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

    } catch (error) {
      logger.error('Error fetching RID Plan parcels', { error });
      res.status(500).json({ 
        error: 'Failed to fetch parcels',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Get parcel by ID
router.get('/parcels/:id',
  authenticateJWT,
  asyncHandler(async (req, res) => {
    const { id } = req.params;

    try {
      const result = await AppDataSource.query(`
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

    } catch (error) {
      logger.error('Error fetching parcel', { error, id });
      res.status(500).json({ 
        error: 'Failed to fetch parcel',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Get aggregated statistics
router.get('/statistics',
  authenticateJWT,
  [
    query('groupBy').optional().isIn(['amphoe', 'tambon', 'cropType', 'zone']),
    query('amphoe').optional().isString(),
    query('tambon').optional().isString(),
  ],
  asyncHandler(async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { groupBy = 'amphoe', amphoe, tambon } = req.query;

    try {
      let groupColumn: string;
      let groupExpression: string;

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

      const params: any[] = [];
      let paramCount = 0;

      // Add filters
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

      const stats = await AppDataSource.query(query, params);

      // Get overall summary
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

      const summary = await AppDataSource.query(summaryQuery);

      res.json({
        summary: summary[0],
        statistics: stats,
        groupedBy: groupBy
      });

    } catch (error) {
      logger.error('Error fetching statistics', { error });
      res.status(500).json({ 
        error: 'Failed to fetch statistics',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Search parcels by location name
router.get('/search',
  authenticateJWT,
  [
    query('q').notEmpty().isString().trim(),
    query('type').optional().isIn(['amphoe', 'tambon', 'both']).default('both'),
    query('limit').optional().isInt({ min: 1, max: 50 }).default(10),
  ],
  asyncHandler(async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { q, type = 'both', limit = 10 } = req.query;

    try {
      let results: any[] = [];

      // Search in amphoe
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
        const amphoeResults = await AppDataSource.query(amphoeQuery, [`%${q}%`, limit]);
        results = results.concat(amphoeResults.map((r: any) => ({ ...r, type: 'amphoe' })));
      }

      // Search in tambon
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
        const tambonResults = await AppDataSource.query(tambonQuery, [`%${q}%`, limit]);
        results = results.concat(tambonResults.map((r: any) => ({ ...r, type: 'tambon' })));
      }

      res.json({
        query: q,
        results: results.slice(0, Number(limit))
      });

    } catch (error) {
      logger.error('Error searching locations', { error });
      res.status(500).json({ 
        error: 'Failed to search locations',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Get water demand analysis
router.get('/water-demand',
  authenticateJWT,
  [
    query('amphoe').optional().isString(),
    query('tambon').optional().isString(),
    query('month').optional().isInt({ min: 1, max: 12 }),
  ],
  asyncHandler(async (req, res) => {
    const errors = validationResult(req);
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

      const params: any[] = [];
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

      // If month is specified, calculate monthly demand (simplified)
      if (month) {
        // Assuming seasonal demand is distributed across 4 months
        query = query.replace(
          'total_seasonal_water_m3',
          'total_seasonal_water_m3 / 4 as monthly_water_m3'
        );
      }

      query += ` GROUP BY properties->'location'->>'amphoe', properties->'location'->>'tambon'
                 ORDER BY total_seasonal_water_m3 DESC`;

      const waterDemand = await AppDataSource.query(query, params);

      // Calculate totals
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

      const totals = await AppDataSource.query(totalQuery + 
        (amphoe ? ` AND properties->'location'->>'amphoe' = $1` : '') +
        (tambon ? ` AND properties->'location'->>'tambon' = $${amphoe ? 2 : 1}` : ''),
        params
      );

      res.json({
        waterDemand,
        summary: {
          totalWaterDemandM3: totals[0].grand_total_water_m3,
          totalAreaRai: totals[0].grand_total_area_rai,
          waterDemandPerRai: totals[0].grand_total_water_m3 / totals[0].grand_total_area_rai,
          month: month ? Number(month) : null
        }
      });

    } catch (error) {
      logger.error('Error calculating water demand', { error });
      res.status(500).json({ 
        error: 'Failed to calculate water demand',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

export default router;