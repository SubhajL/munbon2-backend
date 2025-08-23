import { pool } from '@config/database';
import { logger } from '@utils/logger';
import { waterDemandService } from './water-demand.service';
import { waterLevelAggregationService } from './water-level-aggregation.service';
import * as cron from 'node-cron';
import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import isoWeek from 'dayjs/plugin/isoWeek';

dayjs.extend(weekOfYear);
dayjs.extend(isoWeek);

export interface CropWeekTransition {
  areaId: string;
  areaType: string;
  areaRai: number;
  cropType: string;
  previousCropWeek: number;
  newCropWeek: number;
  plantingDate: Date;
  calendarWeek: number;
  calendarYear: number;
}

export class WeeklyUpdateSchedulerService {
  private scheduledTask: cron.ScheduledTask | null = null;

  /**
   * Start the weekly scheduler
   * Runs every Sunday at 23:00 (11 PM)
   */
  startScheduler(): void {
    // Schedule for every Sunday at 23:00
    this.scheduledTask = cron.schedule('0 23 * * 0', async () => {
      logger.info('Weekly water demand update started');
      try {
        await this.runWeeklyUpdate();
      } catch (error) {
        logger.error('Weekly update failed', error);
      }
    });

    logger.info('Weekly update scheduler started (Sundays at 23:00)');
  }

  /**
   * Stop the scheduler
   */
  stopScheduler(): void {
    if (this.scheduledTask) {
      this.scheduledTask.stop();
      this.scheduledTask = null;
      logger.info('Weekly update scheduler stopped');
    }
  }

  /**
   * Run weekly update process
   */
  async runWeeklyUpdate(): Promise<void> {
    const startTime = Date.now();
    const currentDate = dayjs();
    const completedWeek = currentDate.isoWeek();
    const completedYear = currentDate.year();

    try {
      logger.info('Starting weekly update process', {
        completedWeek,
        completedYear,
        date: currentDate.format('YYYY-MM-DD')
      });

      // Step 1: Get all active crops entering a new week
      const cropsToUpdate = await this.getActiveCropsForUpdate(currentDate.toDate());
      logger.info(`Found ${cropsToUpdate.length} crops to update`);

      // Step 2: Aggregate water levels for the completed week
      const areas = cropsToUpdate.map(crop => ({
        areaId: crop.areaId,
        areaType: crop.areaType
      }));
      
      const uniqueAreas = this.getUniqueAreas(areas);
      await waterLevelAggregationService.aggregateMultipleAreas(
        uniqueAreas,
        completedWeek,
        completedYear
      );

      // Step 3: Recalculate water demand for each crop
      let successCount = 0;
      let failureCount = 0;

      for (const crop of cropsToUpdate) {
        try {
          await this.recalculateWaterDemandWithWaterLevel(crop, completedWeek, completedYear);
          successCount++;
        } catch (error) {
          logger.error('Failed to update crop', { crop, error });
          failureCount++;
        }
      }

      const duration = Date.now() - startTime;
      logger.info('Weekly update completed', {
        duration,
        totalCrops: cropsToUpdate.length,
        successCount,
        failureCount
      });

      // Store update summary
      await this.storeUpdateSummary(
        completedWeek,
        completedYear,
        cropsToUpdate.length,
        successCount,
        failureCount,
        duration
      );

    } catch (error) {
      logger.error('Weekly update process failed', error);
      throw error;
    }
  }

  /**
   * Get active crops that need updating
   */
  private async getActiveCropsForUpdate(currentDate: Date): Promise<CropWeekTransition[]> {
    try {
      const query = `
        WITH active_crops AS (
          SELECT DISTINCT
            wdc.area_id,
            wdc.area_type,
            wdc.area_rai,
            wdc.crop_type,
            wdc.crop_week,
            cc.planting_date,
            cc.total_crop_weeks,
            EXTRACT(DAYS FROM ($1::date - cc.planting_date::date)) as days_since_planting,
            FLOOR(EXTRACT(DAYS FROM ($1::date - cc.planting_date::date)) / 7) + 1 as current_crop_week
          FROM ros.water_demand_calculations wdc
          INNER JOIN ros.crop_calendar cc ON 
            wdc.area_id = cc.area_id AND 
            wdc.area_type = cc.area_type AND
            wdc.crop_type = cc.crop_type
          WHERE cc.status = 'active'
            AND $1::date BETWEEN cc.planting_date AND cc.expected_harvest_date
        )
        SELECT 
          area_id,
          area_type,
          area_rai,
          crop_type,
          current_crop_week - 1 as previous_crop_week,
          current_crop_week as new_crop_week,
          planting_date,
          EXTRACT(WEEK FROM $1::date) as calendar_week,
          EXTRACT(YEAR FROM $1::date) as calendar_year
        FROM active_crops
        WHERE current_crop_week > crop_week
          AND current_crop_week <= total_crop_weeks
      `;

      const result = await pool.query(query, [currentDate]);
      
      return result.rows.map(row => ({
        areaId: row.area_id,
        areaType: row.area_type,
        areaRai: parseFloat(row.area_rai),
        cropType: row.crop_type,
        previousCropWeek: parseInt(row.previous_crop_week),
        newCropWeek: parseInt(row.new_crop_week),
        plantingDate: row.planting_date,
        calendarWeek: parseInt(row.calendar_week),
        calendarYear: parseInt(row.calendar_year)
      }));
    } catch (error) {
      logger.error('Failed to get active crops for update', error);
      throw error;
    }
  }

  /**
   * Recalculate water demand with actual weekly water level
   */
  private async recalculateWaterDemandWithWaterLevel(
    crop: CropWeekTransition,
    calendarWeek: number,
    calendarYear: number
  ): Promise<void> {
    try {
      // Get the aggregated weekly water level
      const weeklyWaterLevel = await waterLevelAggregationService.getWeeklyWaterLevel(
        crop.areaId,
        crop.areaType,
        calendarWeek,
        calendarYear
      );

      // Recalculate water demand with the weekly average water level
      const waterDemandInput = {
        areaId: crop.areaId,
        cropType: crop.cropType as any,
        areaType: crop.areaType as any,
        areaRai: crop.areaRai,
        cropWeek: crop.previousCropWeek, // Use the week that just completed
        calendarWeek,
        calendarYear,
        waterLevel: weeklyWaterLevel?.avgWaterLevelM
      };

      const result = await waterDemandService.calculateWaterDemand(waterDemandInput);

      // Update the calculation timestamp
      await this.updateRecalculationTimestamp(
        crop.areaId,
        crop.areaType,
        crop.cropType,
        crop.previousCropWeek,
        calendarWeek,
        calendarYear
      );

      logger.info('Recalculated water demand with water level', {
        areaId: crop.areaId,
        cropWeek: crop.previousCropWeek,
        waterLevel: weeklyWaterLevel?.avgWaterLevelM,
        adjustmentFactor: result.waterLevelAdjustmentFactor,
        originalDemand: result.netWaterDemandM3,
        adjustedDemand: result.adjustedNetDemandM3
      });

    } catch (error) {
      logger.error('Failed to recalculate water demand', { crop, error });
      throw error;
    }
  }

  /**
   * Update recalculation timestamp
   */
  private async updateRecalculationTimestamp(
    areaId: string,
    areaType: string,
    cropType: string,
    cropWeek: number,
    calendarWeek: number,
    calendarYear: number
  ): Promise<void> {
    const query = `
      UPDATE ros.water_demand_calculations
      SET recalculated_at = CURRENT_TIMESTAMP
      WHERE area_id = $1
        AND area_type = $2
        AND crop_type = $3
        AND crop_week = $4
        AND calendar_week = $5
        AND calendar_year = $6
    `;

    await pool.query(query, [
      areaId,
      areaType,
      cropType,
      cropWeek,
      calendarWeek,
      calendarYear
    ]);
  }

  /**
   * Store update summary for monitoring
   */
  private async storeUpdateSummary(
    week: number,
    year: number,
    totalCrops: number,
    successCount: number,
    failureCount: number,
    durationMs: number
  ): Promise<void> {
    const query = `
      INSERT INTO ros.weekly_update_summary (
        calendar_week, calendar_year, update_date,
        total_crops, success_count, failure_count,
        duration_ms, status
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `;

    const status = failureCount === 0 ? 'success' : 
                   failureCount < totalCrops ? 'partial' : 'failed';

    await pool.query(query, [
      week,
      year,
      new Date(),
      totalCrops,
      successCount,
      failureCount,
      durationMs,
      status
    ]);
  }

  /**
   * Get unique areas from list
   */
  private getUniqueAreas(areas: Array<{ areaId: string; areaType: string }>): Array<{ areaId: string; areaType: string }> {
    const uniqueMap = new Map<string, { areaId: string; areaType: string }>();
    
    areas.forEach(area => {
      const key = `${area.areaId}_${area.areaType}`;
      if (!uniqueMap.has(key)) {
        uniqueMap.set(key, area);
      }
    });

    return Array.from(uniqueMap.values());
  }

  /**
   * Manual trigger for testing or recovery
   */
  async runManualUpdate(week: number, year: number): Promise<void> {
    logger.info('Running manual weekly update', { week, year });
    
    // Calculate the date for the specified week
    const targetDate = dayjs().year(year).isoWeek(week).endOf('isoWeek');
    
    // Run the update process
    await this.runWeeklyUpdate();
  }
}

export const weeklyUpdateScheduler = new WeeklyUpdateSchedulerService();