import { pool } from '@config/database';
import { logger } from '@utils/logger';
import { 
  PlotInfo, 
  PlotCropSchedule, 
  UpdatePlotPlantingDateInput,
  BatchUpdatePlantingDatesInput,
  PlotCurrentCropView
} from '@/types/plot.types';
import { plotWaterDemandService } from './plot-water-demand.service';

class PlotPlantingDateService {
  /**
   * Update planting date for a single plot
   */
  async updatePlotPlantingDate(input: UpdatePlotPlantingDateInput): Promise<PlotInfo> {
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      const { plotId, plantingDate, cropType, season = 'wet', status = 'active' } = input;
      
      // Update plot with current planting info
      const updatePlotQuery = `
        UPDATE ros.plots
        SET 
          current_planting_date = $1,
          current_crop_type = $2,
          current_crop_status = $3,
          updated_at = NOW()
        WHERE plot_id = $4
        RETURNING *
      `;
      
      const plotResult = await client.query(updatePlotQuery, [
        plantingDate,
        cropType,
        status,
        plotId
      ]);
      
      if (plotResult.rows.length === 0) {
        throw new Error(`Plot ${plotId} not found`);
      }
      
      // Calculate expected harvest date (16 weeks for rice)
      const harvestWeeks = cropType === 'rice' ? 16 : 14; // Rice: 16 weeks, others: 14 weeks
      const expectedHarvestDate = new Date(plantingDate);
      expectedHarvestDate.setDate(expectedHarvestDate.getDate() + (harvestWeeks * 7));
      
      // Insert or update crop schedule
      const scheduleQuery = `
        INSERT INTO ros.plot_crop_schedule (
          plot_id, crop_type, planting_date, expected_harvest_date,
          season, year, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (plot_id, year, season)
        DO UPDATE SET
          crop_type = EXCLUDED.crop_type,
          planting_date = EXCLUDED.planting_date,
          expected_harvest_date = EXCLUDED.expected_harvest_date,
          status = EXCLUDED.status,
          updated_at = NOW()
      `;
      
      await client.query(scheduleQuery, [
        plotId,
        cropType,
        plantingDate,
        expectedHarvestDate,
        season,
        new Date(plantingDate).getFullYear(),
        status
      ]);
      
      // Trigger water demand recalculation
      await plotWaterDemandService.calculatePlotWaterDemand({
        plotId,
        cropType: cropType as any,
        plantingDate,
        includeRainfall: true,
        includeLandPreparation: true
      });
      
      await client.query('COMMIT');
      
      return plotResult.rows[0];
      
    } catch (error) {
      await client.query('ROLLBACK');
      logger.error('Error updating plot planting date', error);
      throw error;
    } finally {
      client.release();
    }
  }
  
  /**
   * Batch update planting dates for multiple plots
   */
  async batchUpdatePlantingDates(input: BatchUpdatePlantingDatesInput): Promise<number> {
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      const { plotIds, plantingDate, cropType, season = 'wet', status = 'active' } = input;
      
      // Update all plots
      const updateQuery = `
        UPDATE ros.plots
        SET 
          current_planting_date = $1,
          current_crop_type = $2,
          current_crop_status = $3,
          updated_at = NOW()
        WHERE plot_id = ANY($4::varchar[])
      `;
      
      const result = await client.query(updateQuery, [
        plantingDate,
        cropType,
        status,
        plotIds
      ]);
      
      // Calculate expected harvest date
      const harvestWeeks = cropType === 'rice' ? 16 : 14;
      const expectedHarvestDate = new Date(plantingDate);
      expectedHarvestDate.setDate(expectedHarvestDate.getDate() + (harvestWeeks * 7));
      
      // Batch insert/update crop schedules
      const scheduleQuery = `
        INSERT INTO ros.plot_crop_schedule (
          plot_id, crop_type, planting_date, expected_harvest_date,
          season, year, status
        )
        SELECT 
          unnest($1::varchar[]),
          $2,
          $3,
          $4,
          $5,
          $6,
          $7
        ON CONFLICT (plot_id, year, season)
        DO UPDATE SET
          crop_type = EXCLUDED.crop_type,
          planting_date = EXCLUDED.planting_date,
          expected_harvest_date = EXCLUDED.expected_harvest_date,
          status = EXCLUDED.status,
          updated_at = NOW()
      `;
      
      await client.query(scheduleQuery, [
        plotIds,
        cropType,
        plantingDate,
        expectedHarvestDate,
        season,
        new Date(plantingDate).getFullYear(),
        status
      ]);
      
      await client.query('COMMIT');
      
      // Trigger batch water demand recalculation in background
      setImmediate(async () => {
        try {
          await plotWaterDemandService.calculateBatchPlotWaterDemand({
            plotIds,
            cropType: cropType as any,
            plantingDate,
            includeRainfall: true,
            includeLandPreparation: true
          });
        } catch (error) {
          logger.error('Error in background water demand calculation', error);
        }
      });
      
      return result.rowCount;
      
    } catch (error) {
      await client.query('ROLLBACK');
      logger.error('Error batch updating planting dates', error);
      throw error;
    } finally {
      client.release();
    }
  }
  
  /**
   * Get plots by planting date range
   */
  async getPlotsByPlantingDateRange(
    startDate: Date,
    endDate: Date,
    zoneId?: string
  ): Promise<PlotCurrentCropView[]> {
    let query = `
      SELECT * FROM ros.v_plots_current_crop
      WHERE current_planting_date BETWEEN $1 AND $2
    `;
    
    const params: any[] = [startDate, endDate];
    
    if (zoneId) {
      query += ' AND parent_zone_id = $3';
      params.push(zoneId);
    }
    
    query += ' ORDER BY current_planting_date, plot_id';
    
    const result = await pool.query(query, params);
    
    return result.rows.map(row => ({
      plotId: row.plot_id,
      plotCode: row.plot_code,
      areaRai: parseFloat(row.area_rai),
      parentZoneId: row.parent_zone_id,
      parentSectionId: row.parent_section_id,
      currentPlantingDate: row.current_planting_date,
      currentCropType: row.current_crop_type,
      currentCropStatus: row.current_crop_status,
      totalWaterDemandM3: parseFloat(row.total_water_demand_m3),
      totalNetWaterDemandM3: parseFloat(row.total_net_water_demand_m3),
      landPreparationM3: parseFloat(row.land_preparation_m3),
      currentCropWeek: row.current_crop_week,
      expectedHarvestDate: row.expected_harvest_date
    }));
  }
  
  /**
   * Get upcoming planting schedules
   */
  async getUpcomingPlantingSchedules(daysAhead: number = 30): Promise<PlotCropSchedule[]> {
    const query = `
      SELECT * FROM ros.plot_crop_schedule
      WHERE planting_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '${daysAhead} days'
        AND status = 'planned'
      ORDER BY planting_date, plot_id
    `;
    
    const result = await pool.query(query);
    
    return result.rows.map(row => ({
      id: row.id,
      plotId: row.plot_id,
      cropType: row.crop_type,
      plantingDate: row.planting_date,
      expectedHarvestDate: row.expected_harvest_date,
      season: row.season,
      year: row.year,
      status: row.status,
      createdAt: row.created_at,
      updatedAt: row.updated_at
    }));
  }
  
  /**
   * Update crop status (e.g., from active to harvested)
   */
  async updateCropStatus(plotId: string, status: string): Promise<void> {
    const query = `
      UPDATE ros.plots
      SET 
        current_crop_status = $1,
        updated_at = NOW()
      WHERE plot_id = $2
    `;
    
    await pool.query(query, [status, plotId]);
    
    // Also update in schedule table
    const scheduleQuery = `
      UPDATE ros.plot_crop_schedule
      SET 
        status = $1,
        updated_at = NOW()
      WHERE plot_id = $2 
        AND status = 'active'
    `;
    
    await pool.query(scheduleQuery, [
      status === 'harvested' ? 'completed' : status,
      plotId
    ]);
  }
  
  /**
   * Get plots ready for harvest
   */
  async getPlotsReadyForHarvest(daysWindow: number = 7): Promise<PlotCurrentCropView[]> {
    const query = `
      SELECT * FROM ros.v_plots_current_crop
      WHERE current_crop_status = 'active'
        AND expected_harvest_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '${daysWindow} days'
      ORDER BY expected_harvest_date, plot_id
    `;
    
    const result = await pool.query(query);
    
    return result.rows.map(row => ({
      plotId: row.plot_id,
      plotCode: row.plot_code,
      areaRai: parseFloat(row.area_rai),
      parentZoneId: row.parent_zone_id,
      parentSectionId: row.parent_section_id,
      currentPlantingDate: row.current_planting_date,
      currentCropType: row.current_crop_type,
      currentCropStatus: row.current_crop_status,
      totalWaterDemandM3: parseFloat(row.total_water_demand_m3),
      totalNetWaterDemandM3: parseFloat(row.total_net_water_demand_m3),
      landPreparationM3: parseFloat(row.land_preparation_m3),
      currentCropWeek: row.current_crop_week,
      expectedHarvestDate: row.expected_harvest_date
    }));
  }
}

export const plotPlantingDateService = new PlotPlantingDateService();