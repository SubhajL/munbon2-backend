import { Router, Request, Response } from 'express';
import { query, body, param, validationResult } from 'express-validator';
import { AppDataSource } from '../config/database';
import { logger } from '../utils/logger';
import { authenticateJWT } from '../middleware/auth';
import { asyncHandler } from '../middleware/async-handler';

const router = Router();

// Create or update ROS water demand calculation
router.post('/demands',
  authenticateJWT,
  [
    body('parcelId').optional().isUUID(),
    body('sectionId').notEmpty().isString(),
    body('calculationDate').notEmpty().isISO8601(),
    body('calendarWeek').notEmpty().isInt({ min: 1, max: 53 }),
    body('calendarYear').notEmpty().isInt({ min: 2020 }),
    body('cropType').notEmpty().isString(),
    body('areaRai').notEmpty().isFloat({ min: 0 }),
    body('grossDemandM3').notEmpty().isFloat({ min: 0 }),
    body('netDemandM3').notEmpty().isFloat({ min: 0 }),
  ],
  asyncHandler(async (req: Request, res: Response) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const demand = req.body;
    
    try {
      // First, try to find parcel by section ID if parcelId not provided
      let parcelId = demand.parcelId;
      if (!parcelId && demand.sectionId) {
        const parcelResult = await AppDataSource.query(
          `SELECT id FROM gis.agricultural_plots 
           WHERE plot_code = $1 OR properties->>'externalId' = $1 
           LIMIT 1`,
          [demand.sectionId]
        );
        
        if (parcelResult.length > 0) {
          parcelId = parcelResult[0].id;
        }
      }
      
      const query = `
        INSERT INTO gis.ros_water_demands (
          parcel_id, section_id, calculation_date, calendar_week, calendar_year,
          crop_type, crop_week, growth_stage, planting_date, harvest_date,
          area_rai, et0_mm, kc_factor, percolation_mm,
          gross_demand_mm, gross_demand_m3, effective_rainfall_mm,
          net_demand_mm, net_demand_m3,
          moisture_deficit_percent, stress_level
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
          $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
        )
        ON CONFLICT (parcel_id, calendar_week, calendar_year) 
        DO UPDATE SET
          calculation_date = EXCLUDED.calculation_date,
          crop_type = EXCLUDED.crop_type,
          crop_week = EXCLUDED.crop_week,
          growth_stage = EXCLUDED.growth_stage,
          planting_date = EXCLUDED.planting_date,
          harvest_date = EXCLUDED.harvest_date,
          area_rai = EXCLUDED.area_rai,
          et0_mm = EXCLUDED.et0_mm,
          kc_factor = EXCLUDED.kc_factor,
          percolation_mm = EXCLUDED.percolation_mm,
          gross_demand_mm = EXCLUDED.gross_demand_mm,
          gross_demand_m3 = EXCLUDED.gross_demand_m3,
          effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
          net_demand_mm = EXCLUDED.net_demand_mm,
          net_demand_m3 = EXCLUDED.net_demand_m3,
          moisture_deficit_percent = EXCLUDED.moisture_deficit_percent,
          stress_level = EXCLUDED.stress_level,
          updated_at = CURRENT_TIMESTAMP
        RETURNING *`;
      
      const values = [
        parcelId,
        demand.sectionId,
        demand.calculationDate,
        demand.calendarWeek,
        demand.calendarYear,
        demand.cropType,
        demand.cropWeek || null,
        demand.growthStage || null,
        demand.plantingDate || null,
        demand.harvestDate || null,
        demand.areaRai,
        demand.et0Mm || null,
        demand.kcFactor || null,
        demand.percolationMm || 14,
        demand.grossDemandMm || null,
        demand.grossDemandM3,
        demand.effectiveRainfallMm || 0,
        demand.netDemandMm || null,
        demand.netDemandM3,
        demand.moistureDeficitPercent || null,
        demand.stressLevel || null
      ];
      
      const result = await AppDataSource.query(query, values);
      
      logger.info('ROS water demand saved', {
        sectionId: demand.sectionId,
        week: demand.calendarWeek,
        year: demand.calendarYear
      });
      
      res.json({
        success: true,
        data: result[0]
      });
      
    } catch (error) {
      logger.error('Error saving ROS water demand', { error });
      res.status(500).json({
        error: 'Failed to save water demand calculation',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Bulk insert/update ROS water demands
router.post('/demands/bulk',
  authenticateJWT,
  [
    body('demands').isArray({ min: 1 }),
    body('demands.*.sectionId').notEmpty().isString(),
    body('demands.*.calendarWeek').notEmpty().isInt({ min: 1, max: 53 }),
    body('demands.*.calendarYear').notEmpty().isInt({ min: 2020 }),
  ],
  asyncHandler(async (req: Request, res: Response) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { demands } = req.body;
    const results = [];
    
    // Use transaction for bulk operations
    const queryRunner = AppDataSource.createQueryRunner();
    await queryRunner.connect();
    await queryRunner.startTransaction();
    
    try {
      for (const demand of demands) {
        // Find parcel ID if not provided
        let parcelId = demand.parcelId;
        if (!parcelId && demand.sectionId) {
          const parcelResult = await queryRunner.query(
            `SELECT id FROM gis.agricultural_plots 
             WHERE plot_code = $1 OR properties->>'externalId' = $1 
             LIMIT 1`,
            [demand.sectionId]
          );
          
          if (parcelResult.length > 0) {
            parcelId = parcelResult[0].id;
          }
        }
        
        const query = `
          INSERT INTO gis.ros_water_demands (
            parcel_id, section_id, calculation_date, calendar_week, calendar_year,
            crop_type, crop_week, growth_stage, planting_date, harvest_date,
            area_rai, et0_mm, kc_factor, percolation_mm,
            gross_demand_mm, gross_demand_m3, effective_rainfall_mm,
            net_demand_mm, net_demand_m3,
            moisture_deficit_percent, stress_level
          ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
          )
          ON CONFLICT (parcel_id, calendar_week, calendar_year) 
          DO UPDATE SET
            calculation_date = EXCLUDED.calculation_date,
            crop_type = EXCLUDED.crop_type,
            crop_week = EXCLUDED.crop_week,
            growth_stage = EXCLUDED.growth_stage,
            planting_date = EXCLUDED.planting_date,
            harvest_date = EXCLUDED.harvest_date,
            area_rai = EXCLUDED.area_rai,
            et0_mm = EXCLUDED.et0_mm,
            kc_factor = EXCLUDED.kc_factor,
            percolation_mm = EXCLUDED.percolation_mm,
            gross_demand_mm = EXCLUDED.gross_demand_mm,
            gross_demand_m3 = EXCLUDED.gross_demand_m3,
            effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
            net_demand_mm = EXCLUDED.net_demand_mm,
            net_demand_m3 = EXCLUDED.net_demand_m3,
            moisture_deficit_percent = EXCLUDED.moisture_deficit_percent,
            stress_level = EXCLUDED.stress_level,
            updated_at = CURRENT_TIMESTAMP
          RETURNING id`;
        
        const values = [
          parcelId,
          demand.sectionId,
          demand.calculationDate || new Date().toISOString(),
          demand.calendarWeek,
          demand.calendarYear,
          demand.cropType,
          demand.cropWeek || null,
          demand.growthStage || null,
          demand.plantingDate || null,
          demand.harvestDate || null,
          demand.areaRai,
          demand.et0Mm || null,
          demand.kcFactor || null,
          demand.percolationMm || 14,
          demand.grossDemandMm || null,
          demand.grossDemandM3,
          demand.effectiveRainfallMm || 0,
          demand.netDemandMm || null,
          demand.netDemandM3,
          demand.moistureDeficitPercent || null,
          demand.stressLevel || null
        ];
        
        const result = await queryRunner.query(query, values);
        results.push(result[0]);
      }
      
      await queryRunner.commitTransaction();
      
      // Refresh materialized view
      await AppDataSource.query('REFRESH MATERIALIZED VIEW CONCURRENTLY gis.weekly_demand_summary');
      
      logger.info('Bulk ROS water demands saved', {
        count: results.length
      });
      
      res.json({
        success: true,
        count: results.length,
        data: results
      });
      
    } catch (error) {
      await queryRunner.rollbackTransaction();
      logger.error('Error saving bulk ROS water demands', { error });
      res.status(500).json({
        error: 'Failed to save water demand calculations',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    } finally {
      await queryRunner.release();
    }
  })
);

// Get ROS water demands with filters
router.get('/demands',
  authenticateJWT,
  [
    query('sectionId').optional().isString(),
    query('amphoe').optional().isString(),
    query('tambon').optional().isString(),
    query('cropType').optional().isString(),
    query('calendarWeek').optional().isInt({ min: 1, max: 53 }),
    query('calendarYear').optional().isInt({ min: 2020 }),
    query('latest').optional().isBoolean(),
    query('page').optional().isInt({ min: 1 }).default(1),
    query('limit').optional().isInt({ min: 1, max: 100 }).default(20),
  ],
  asyncHandler(async (req: Request, res: Response) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const {
      sectionId,
      amphoe,
      tambon,
      cropType,
      calendarWeek,
      calendarYear,
      latest = false,
      page = 1,
      limit = 20
    } = req.query;
    
    try {
      let query = `
        SELECT 
          rwd.*,
          p.plot_code,
          p.properties->>'amphoe' as amphoe,
          p.properties->>'tambon' as tambon,
          ST_AsGeoJSON(p.boundary) as geometry
        FROM gis.ros_water_demands rwd
        LEFT JOIN gis.agricultural_plots p ON rwd.parcel_id = p.id
        WHERE 1=1
      `;
      
      const values: any[] = [];
      let paramCount = 0;
      
      if (sectionId) {
        paramCount++;
        query += ` AND rwd.section_id = $${paramCount}`;
        values.push(sectionId);
      }
      
      if (amphoe) {
        paramCount++;
        query += ` AND p.properties->>'amphoe' = $${paramCount}`;
        values.push(amphoe);
      }
      
      if (tambon) {
        paramCount++;
        query += ` AND p.properties->>'tambon' = $${paramCount}`;
        values.push(tambon);
      }
      
      if (cropType) {
        paramCount++;
        query += ` AND rwd.crop_type = $${paramCount}`;
        values.push(cropType);
      }
      
      if (calendarWeek) {
        paramCount++;
        query += ` AND rwd.calendar_week = $${paramCount}`;
        values.push(calendarWeek);
      }
      
      if (calendarYear) {
        paramCount++;
        query += ` AND rwd.calendar_year = $${paramCount}`;
        values.push(calendarYear);
      }
      
      // If latest is true, get only the most recent calculation per parcel
      if (latest === 'true') {
        query = `
          WITH latest_demands AS (
            SELECT DISTINCT ON (parcel_id) *
            FROM gis.ros_water_demands
            ORDER BY parcel_id, calculation_date DESC
          )
          SELECT 
            ld.*,
            p.plot_code,
            p.properties->>'amphoe' as amphoe,
            p.properties->>'tambon' as tambon,
            ST_AsGeoJSON(p.boundary) as geometry
          FROM latest_demands ld
          LEFT JOIN gis.parcels p ON ld.parcel_id = p.id
          WHERE 1=1
        `;
        // Re-apply filters would go here
      }
      
      // Get total count
      const countQuery = query.replace(/SELECT[\s\S]*?FROM/, 'SELECT COUNT(*) as total FROM');
      const countResult = await AppDataSource.query(countQuery, values);
      const total = parseInt(countResult[0].total);
      
      // Add ordering and pagination
      query += ` ORDER BY rwd.calculation_date DESC`;
      
      const offset = (Number(page) - 1) * Number(limit);
      paramCount++;
      query += ` LIMIT $${paramCount}`;
      values.push(limit);
      paramCount++;
      query += ` OFFSET $${paramCount}`;
      values.push(offset);
      
      const result = await AppDataSource.query(query, values);
      
      res.json({
        success: true,
        data: result.map((row: any) => ({
          ...row,
          geometry: row.geometry ? JSON.parse(row.geometry) : null
        })),
        pagination: {
          page: Number(page),
          limit: Number(limit),
          total,
          totalPages: Math.ceil(total / Number(limit))
        }
      });
      
    } catch (error) {
      logger.error('Error fetching ROS water demands', { error });
      res.status(500).json({
        error: 'Failed to fetch water demand calculations',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Get weekly demand summary
router.get('/demands/summary',
  authenticateJWT,
  [
    query('year').optional().isInt({ min: 2020 }),
    query('week').optional().isInt({ min: 1, max: 53 }),
    query('amphoe').optional().isString(),
    query('cropType').optional().isString(),
  ],
  asyncHandler(async (req: Request, res: Response) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { year, week, amphoe, cropType } = req.query;
    
    try {
      let query = `
        SELECT *
        FROM gis.weekly_demand_summary
        WHERE 1=1
      `;
      
      const values: any[] = [];
      let paramCount = 0;
      
      if (year) {
        paramCount++;
        query += ` AND calendar_year = $${paramCount}`;
        values.push(year);
      }
      
      if (week) {
        paramCount++;
        query += ` AND calendar_week = $${paramCount}`;
        values.push(week);
      }
      
      if (amphoe) {
        paramCount++;
        query += ` AND amphoe = $${paramCount}`;
        values.push(amphoe);
      }
      
      if (cropType) {
        paramCount++;
        query += ` AND crop_type = $${paramCount}`;
        values.push(cropType);
      }
      
      query += ` ORDER BY calendar_year DESC, calendar_week DESC, total_net_demand_m3 DESC`;
      
      const result = await AppDataSource.query(query, values);
      
      res.json({
        success: true,
        data: result
      });
      
    } catch (error) {
      logger.error('Error fetching demand summary', { error });
      res.status(500).json({
        error: 'Failed to fetch demand summary',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

// Compare ROS calculations with RID Plan demands
router.get('/demands/comparison',
  authenticateJWT,
  [
    query('amphoe').optional().isString(),
    query('tambon').optional().isString(),
    query('week').optional().isInt({ min: 1, max: 53 }),
    query('year').optional().isInt({ min: 2020 }),
  ],
  asyncHandler(async (req: Request, res: Response) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { amphoe, tambon, week, year } = req.query;
    
    try {
      let query = `
        SELECT 
          p.id,
          p.plot_code,
          p.properties->>'amphoe' as amphoe,
          p.properties->>'tambon' as tambon,
          p.area_hectares * 6.25 as area_rai,
          p.properties->'ridAttributes'->>'plantId' as rid_crop_type,
          CAST(p.properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) as season_irr_m3_per_rai,
          CAST(p.properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) * p.area_hectares * 6.25 as rid_total_demand_m3,
          rwd.crop_type as ros_crop_type,
          rwd.net_demand_m3 as ros_net_demand_m3,
          rwd.growth_stage,
          rwd.moisture_deficit_percent,
          rwd.stress_level,
          (rwd.net_demand_m3 - (CAST(p.properties->'ridAttributes'->>'seasonIrrM3PerRai' AS FLOAT) * p.area_hectares * 6.25 / 16)) as weekly_difference_m3
        FROM gis.agricultural_plots p
        LEFT JOIN gis.ros_water_demands rwd ON p.id = rwd.parcel_id
        WHERE p.properties->>'uploadId' LIKE 'ridplan-%'
      `;
      
      const values: any[] = [];
      let paramCount = 0;
      
      if (amphoe) {
        paramCount++;
        query += ` AND p.properties->>'amphoe' = $${paramCount}`;
        values.push(amphoe);
      }
      
      if (tambon) {
        paramCount++;
        query += ` AND p.properties->>'tambon' = $${paramCount}`;
        values.push(tambon);
      }
      
      if (week && year) {
        paramCount++;
        query += ` AND rwd.calendar_week = $${paramCount}`;
        values.push(week);
        paramCount++;
        query += ` AND rwd.calendar_year = $${paramCount}`;
        values.push(year);
      }
      
      query += ` ORDER BY ABS(weekly_difference_m3) DESC NULLS LAST LIMIT 100`;
      
      const result = await AppDataSource.query(query, values);
      
      res.json({
        success: true,
        data: result,
        summary: {
          totalParcels: result.length,
          avgDifferenceM3: result.reduce((sum: number, row: any) => sum + (row.weekly_difference_m3 || 0), 0) / result.length
        }
      });
      
    } catch (error) {
      logger.error('Error fetching demand comparison', { error });
      res.status(500).json({
        error: 'Failed to fetch demand comparison',
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  })
);

export default router;