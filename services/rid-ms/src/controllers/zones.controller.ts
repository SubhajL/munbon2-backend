import { Request, Response } from 'express';
import { Pool } from 'pg';
import { logger } from '../utils/logger';
import * as turf from '@turf/turf';

export class ZonesController {
  private db: Pool;

  constructor() {
    this.db = new Pool({
      connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres123@localhost:5435/rid_ms',
    });
  }

  /**
   * List all zones with summary statistics
   */
  async listZones(req: Request, res: Response) {
    const { includeStats } = req.query;

    try {
      const query = `
        SELECT DISTINCT zone
        FROM parcels
        WHERE valid_to IS NULL
        ORDER BY zone
      `;

      const result = await this.db.query(query);
      const zones = result.rows.map(r => r.zone);

      if (!includeStats) {
        return res.json({ zones });
      }

      // Get statistics for each zone
      const statsPromises = zones.map(async (zone) => {
        const statsQuery = `
          SELECT 
            COUNT(*) as parcel_count,
            SUM(area_rai) as total_area_rai,
            SUM(area_sqm) as total_area_sqm,
            COUNT(DISTINCT crop_type) as crop_types,
            COUNT(DISTINCT owner_name) as unique_owners
          FROM parcels
          WHERE zone = $1 AND valid_to IS NULL
        `;

        const statsResult = await this.db.query(statsQuery, [zone]);
        const stats = statsResult.rows[0];

        // Get crop distribution
        const cropQuery = `
          SELECT 
            crop_type,
            COUNT(*) as count,
            SUM(area_rai) as area_rai
          FROM parcels
          WHERE zone = $1 AND valid_to IS NULL AND crop_type IS NOT NULL
          GROUP BY crop_type
          ORDER BY area_rai DESC
        `;

        const cropResult = await this.db.query(cropQuery, [zone]);

        return {
          zone,
          stats: {
            parcelCount: parseInt(stats.parcel_count),
            totalAreaRai: parseFloat(stats.total_area_rai || 0),
            totalAreaSqm: parseFloat(stats.total_area_sqm || 0),
            cropTypes: parseInt(stats.crop_types),
            uniqueOwners: parseInt(stats.unique_owners),
            crops: cropResult.rows,
          },
        };
      });

      const zoneStats = await Promise.all(statsPromises);

      res.json({ zones: zoneStats });
    } catch (error) {
      logger.error('Error listing zones:', error);
      res.status(500).json({ error: 'Failed to list zones' });
    }
  }

  /**
   * Get all parcels in a zone
   */
  async getZoneParcels(req: Request, res: Response) {
    const { zone } = req.params;
    const { cropType, waterDemandMethod, limit = 100, offset = 0 } = req.query;

    try {
      let query = `
        SELECT 
          id,
          parcel_id,
          zone,
          sub_zone,
          area_rai,
          crop_type,
          owner_name,
          water_demand_method,
          ST_AsGeoJSON(centroid) as centroid
        FROM parcels
        WHERE zone = $1 AND valid_to IS NULL
      `;

      const params: any[] = [zone];
      let paramCount = 1;

      if (cropType) {
        paramCount++;
        query += ` AND crop_type = $${paramCount}`;
        params.push(cropType);
      }

      if (waterDemandMethod) {
        paramCount++;
        query += ` AND water_demand_method = $${paramCount}`;
        params.push(waterDemandMethod);
      }

      query += ` ORDER BY parcel_id`;

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

      // Get total count
      const countQuery = `
        SELECT COUNT(*) as total
        FROM parcels
        WHERE zone = $1 AND valid_to IS NULL
        ${cropType ? `AND crop_type = $2` : ''}
        ${waterDemandMethod ? `AND water_demand_method = $${cropType ? 3 : 2}` : ''}
      `;

      const countParams = [zone];
      if (cropType) countParams.push(cropType);
      if (waterDemandMethod) countParams.push(waterDemandMethod);

      const countResult = await this.db.query(countQuery, countParams);

      res.json({
        zone,
        parcels,
        pagination: {
          total: parseInt(countResult.rows[0].total),
          limit,
          offset,
        },
      });
    } catch (error) {
      logger.error('Error getting zone parcels:', error);
      res.status(500).json({ error: 'Failed to get zone parcels' });
    }
  }

  /**
   * Get zone summary with water demand
   */
  async getZoneSummary(req: Request, res: Response) {
    const { zone } = req.params;
    const { date } = req.query;

    try {
      // Check if zone exists in summary table
      const summaryDate = date || new Date().toISOString().split('T')[0];
      
      const summaryQuery = `
        SELECT *
        FROM zone_summaries
        WHERE zone = $1 AND summary_date = $2
      `;

      const summaryResult = await this.db.query(summaryQuery, [zone, summaryDate]);

      if (summaryResult.rows.length > 0) {
        const summary = summaryResult.rows[0];
        return res.json({
          zone,
          date: summaryDate,
          totalParcels: summary.total_parcels,
          totalAreaRai: parseFloat(summary.total_area_rai),
          totalAreaSqm: parseFloat(summary.total_area_sqm),
          cropDistribution: summary.crop_distribution,
          waterDemandByMethod: summary.water_demand_by_method,
          totalDailyDemandCubicMeters: parseFloat(summary.total_daily_demand_cubic_meters || 0),
          lastUpdated: summary.updated_at,
        });
      }

      // Calculate fresh summary
      const statsQuery = `
        SELECT 
          COUNT(*) as total_parcels,
          SUM(area_rai) as total_area_rai,
          SUM(area_sqm) as total_area_sqm,
          COUNT(DISTINCT crop_type) as crop_types
        FROM parcels
        WHERE zone = $1 AND valid_to IS NULL
      `;

      const statsResult = await this.db.query(statsQuery, [zone]);
      const stats = statsResult.rows[0];

      // Get crop distribution
      const cropQuery = `
        SELECT 
          crop_type,
          COUNT(*) as count,
          SUM(area_rai) as area_rai
        FROM parcels
        WHERE zone = $1 AND valid_to IS NULL AND crop_type IS NOT NULL
        GROUP BY crop_type
      `;

      const cropResult = await this.db.query(cropQuery, [zone]);
      const cropDistribution = cropResult.rows.reduce((acc, row) => {
        acc[row.crop_type] = {
          count: parseInt(row.count),
          areaRai: parseFloat(row.area_rai),
        };
        return acc;
      }, {});

      // Get water demand by method
      const waterDemandQuery = `
        SELECT 
          p.water_demand_method,
          COUNT(DISTINCT p.id) as parcel_count,
          SUM(wdc.daily_demand_cubic_meters) as total_daily_demand
        FROM parcels p
        LEFT JOIN water_demand_calculations wdc ON p.id = wdc.parcel_id
        WHERE p.zone = $1 AND p.valid_to IS NULL
        GROUP BY p.water_demand_method
      `;

      const waterDemandResult = await this.db.query(waterDemandQuery, [zone]);
      const waterDemandByMethod = waterDemandResult.rows.reduce((acc, row) => {
        acc[row.water_demand_method] = parseFloat(row.total_daily_demand || 0);
        return acc;
      }, {});

      const totalDailyDemand = Object.values(waterDemandByMethod).reduce(
        (sum: number, val: any) => sum + val, 
        0
      );

      res.json({
        zone,
        date: summaryDate,
        totalParcels: parseInt(stats.total_parcels),
        totalAreaRai: parseFloat(stats.total_area_rai || 0),
        totalAreaSqm: parseFloat(stats.total_area_sqm || 0),
        cropTypes: parseInt(stats.crop_types),
        cropDistribution,
        waterDemandByMethod,
        totalDailyDemandCubicMeters: totalDailyDemand,
      });
    } catch (error) {
      logger.error('Error getting zone summary:', error);
      res.status(500).json({ error: 'Failed to get zone summary' });
    }
  }

  /**
   * Export zone as GeoJSON
   */
  async getZoneGeoJSON(req: Request, res: Response) {
    const { zone } = req.params;
    const { includeWaterDemand, simplify, precision = 6 } = req.query;

    try {
      const query = `
        SELECT 
          p.id,
          p.parcel_id,
          p.area_rai,
          p.crop_type,
          p.owner_name,
          p.water_demand_method,
          ST_AsGeoJSON(p.geometry, ${precision}) as geometry
          ${includeWaterDemand ? ', wdc.daily_demand_cubic_meters' : ''}
        FROM parcels p
        ${includeWaterDemand ? 'LEFT JOIN water_demand_calculations wdc ON p.id = wdc.parcel_id' : ''}
        WHERE p.zone = $1 AND p.valid_to IS NULL
      `;

      const result = await this.db.query(query, [zone]);

      const features = result.rows.map(row => {
        const geometry = JSON.parse(row.geometry);
        
        // Optionally simplify geometry
        const finalGeometry = simplify === 'true' 
          ? turf.simplify(geometry, { tolerance: 0.00001, highQuality: false })
          : geometry;

        const properties: any = {
          id: row.id,
          parcelId: row.parcel_id,
          areaRai: parseFloat(row.area_rai),
          cropType: row.crop_type,
          ownerName: row.owner_name,
          waterDemandMethod: row.water_demand_method,
        };

        if (includeWaterDemand && row.daily_demand_cubic_meters) {
          properties.waterDemandDaily = parseFloat(row.daily_demand_cubic_meters);
        }

        return {
          type: 'Feature',
          properties,
          geometry: finalGeometry,
        };
      });

      const geojson = {
        type: 'FeatureCollection',
        features,
        metadata: {
          zone,
          totalFeatures: features.length,
          precision,
          simplified: simplify === 'true',
          includesWaterDemand: includeWaterDemand === 'true',
          generatedAt: new Date().toISOString(),
        },
      };

      res.json(geojson);
    } catch (error) {
      logger.error('Error exporting zone GeoJSON:', error);
      res.status(500).json({ error: 'Failed to export zone GeoJSON' });
    }
  }

  /**
   * Get zone changes over time
   */
  async getZoneChanges(req: Request, res: Response) {
    const { zone } = req.params;
    const { startDate, endDate } = req.query;

    try {
      // Get parcels that changed during the period
      const changesQuery = `
        SELECT 
          parcel_id,
          valid_from,
          valid_to,
          'added' as change_type,
          area_rai,
          crop_type,
          owner_name
        FROM parcels
        WHERE zone = $1 
        AND valid_from >= $2 
        AND valid_from <= $3

        UNION ALL

        SELECT 
          parcel_id,
          valid_from,
          valid_to,
          'removed' as change_type,
          area_rai,
          crop_type,
          owner_name
        FROM parcels
        WHERE zone = $1 
        AND valid_to >= $2 
        AND valid_to <= $3

        ORDER BY valid_from DESC
      `;

      const changesResult = await this.db.query(changesQuery, [zone, startDate, endDate]);

      // Get summary statistics for start and end dates
      const statsQuery = `
        WITH start_stats AS (
          SELECT 
            COUNT(*) as parcel_count,
            SUM(area_rai) as total_area
          FROM parcels
          WHERE zone = $1
          AND valid_from <= $2
          AND (valid_to IS NULL OR valid_to > $2)
        ),
        end_stats AS (
          SELECT 
            COUNT(*) as parcel_count,
            SUM(area_rai) as total_area
          FROM parcels
          WHERE zone = $1
          AND valid_from <= $3
          AND (valid_to IS NULL OR valid_to > $3)
        )
        SELECT 
          start_stats.parcel_count as start_parcels,
          start_stats.total_area as start_area,
          end_stats.parcel_count as end_parcels,
          end_stats.total_area as end_area
        FROM start_stats, end_stats
      `;

      const statsResult = await this.db.query(statsQuery, [zone, startDate, endDate]);
      const stats = statsResult.rows[0];

      res.json({
        zone,
        period: { startDate, endDate },
        summary: {
          startParcels: parseInt(stats.start_parcels || 0),
          endParcels: parseInt(stats.end_parcels || 0),
          parcelChange: parseInt(stats.end_parcels || 0) - parseInt(stats.start_parcels || 0),
          startAreaRai: parseFloat(stats.start_area || 0),
          endAreaRai: parseFloat(stats.end_area || 0),
          areaChangeRai: parseFloat(stats.end_area || 0) - parseFloat(stats.start_area || 0),
        },
        changes: changesResult.rows,
        totalChanges: changesResult.rows.length,
      });
    } catch (error) {
      logger.error('Error getting zone changes:', error);
      res.status(500).json({ error: 'Failed to get zone changes' });
    }
  }
}