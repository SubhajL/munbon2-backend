import { pool } from '@config/database';
import { 
  WaterDemandInput, 
  WaterDemandResult, 
  SeasonalWaterDemandResult,
  CropType
} from '../types';
import { logger } from '@utils/logger';
import { rainfallService } from './rainfall.service';
import { effectiveRainfallService } from './effective-rainfall.service';
import { waterLevelService } from './water-level.service';
import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';

dayjs.extend(weekOfYear);

export class WaterDemandService {
  private readonly PERCOLATION_MM_PER_WEEK = 14;
  private readonly RAI_TO_M3_FACTOR = 1.6;

  /**
   * Calculate water demand for a specific crop week
   */
  async calculateWaterDemand(input: WaterDemandInput): Promise<WaterDemandResult> {
    try {
      // Get monthly ETo for the calendar week
      const monthlyETo = await this.getMonthlyETo(input.calendarWeek, input.calendarYear);
      
      // Calculate weekly ETo
      const weeklyETo = this.calculateWeeklyETo(
        monthlyETo,
        input.calendarWeek,
        input.calendarYear
      );

      // Get Kc value for crop type and week
      const kcValue = await this.getKcValue(input.cropType, input.cropWeek);

      // Calculate water demand
      const cropWaterDemandMm = (weeklyETo * kcValue) + this.PERCOLATION_MM_PER_WEEK;
      const cropWaterDemandM3 = cropWaterDemandMm * input.areaRai * this.RAI_TO_M3_FACTOR;

      // Get effective rainfall if not provided
      let effectiveRainfall = input.effectiveRainfall;
      if (effectiveRainfall === undefined) {
        // Use new effective rainfall service with crop-specific values
        const effectiveRainfallData = await effectiveRainfallService.getEffectiveRainfall(
          input.cropType,
          input.calendarWeek,
          input.calendarYear
        );
        effectiveRainfall = effectiveRainfallData.weeklyEffectiveRainfall;
      }

      // Get current water level if not provided
      let waterLevel = input.waterLevel;
      if (waterLevel === undefined) {
        const currentLevel = await waterLevelService.getCurrentWaterLevel(input.areaId);
        waterLevel = currentLevel?.waterLevelM;
      }

      // Calculate net water demand
      let netWaterDemandMm: number | undefined;
      let netWaterDemandM3: number | undefined;
      
      if (effectiveRainfall !== undefined) {
        netWaterDemandMm = Math.max(0, cropWaterDemandMm - effectiveRainfall);
        netWaterDemandM3 = netWaterDemandMm * input.areaRai * this.RAI_TO_M3_FACTOR;
      }

      const result: WaterDemandResult = {
        areaId: input.areaId,
        areaType: input.areaType,
        areaRai: input.areaRai,
        cropType: input.cropType,
        cropWeek: input.cropWeek,
        calendarWeek: input.calendarWeek,
        calendarYear: input.calendarYear,
        monthlyETo,
        weeklyETo,
        kcValue,
        percolation: this.PERCOLATION_MM_PER_WEEK,
        cropWaterDemandMm,
        cropWaterDemandM3,
        effectiveRainfall,
        waterLevel,
        netWaterDemandMm,
        netWaterDemandM3,
      };

      // Save calculation to database
      await this.saveWaterDemandCalculation(result);

      return result;
    } catch (error) {
      logger.error('Failed to calculate water demand', error);
      throw error;
    }
  }

  /**
   * Calculate water demand for entire crop season
   */
  async calculateSeasonalWaterDemand(
    areaId: string,
    areaType: string,
    areaRai: number,
    cropType: CropType,
    plantingDate: Date,
    includeRainfall: boolean = false
  ): Promise<SeasonalWaterDemandResult> {
    try {
      const totalCropWeeks = await this.getTotalCropWeeks(cropType);
      const harvestDate = dayjs(plantingDate).add(totalCropWeeks, 'week').toDate();
      
      const weeklyResults: WaterDemandResult[] = [];
      let totalWaterDemandMm = 0;
      let totalWaterDemandM3 = 0;
      let totalEffectiveRainfall = 0;
      let totalNetWaterDemandMm = 0;
      let totalNetWaterDemandM3 = 0;

      // Calculate for each crop week
      for (let cropWeek = 1; cropWeek <= totalCropWeeks; cropWeek++) {
        const weekDate = dayjs(plantingDate).add(cropWeek - 1, 'week');
        const calendarWeek = weekDate.week();
        const calendarYear = weekDate.year();

        const input: WaterDemandInput = {
          areaId,
          cropType,
          areaType: areaType as any,
          areaRai,
          cropWeek,
          calendarWeek,
          calendarYear,
        };

        // Add rainfall data if requested
        if (includeRainfall) {
          // TODO: Get actual rainfall data
          input.effectiveRainfall = 0; // Placeholder
        }

        const weekResult = await this.calculateWaterDemand(input);
        weeklyResults.push(weekResult);

        totalWaterDemandMm += weekResult.cropWaterDemandMm;
        totalWaterDemandM3 += weekResult.cropWaterDemandM3;

        if (weekResult.effectiveRainfall !== undefined) {
          totalEffectiveRainfall += weekResult.effectiveRainfall;
          totalNetWaterDemandMm += weekResult.netWaterDemandMm || 0;
          totalNetWaterDemandM3 += weekResult.netWaterDemandM3 || 0;
        }
      }

      return {
        areaId,
        areaType: areaType as any,
        areaRai,
        cropType,
        totalCropWeeks,
        plantingDate,
        harvestDate,
        totalWaterDemandMm,
        totalWaterDemandM3,
        totalEffectiveRainfall: includeRainfall ? totalEffectiveRainfall : undefined,
        totalNetWaterDemandMm: includeRainfall ? totalNetWaterDemandMm : undefined,
        totalNetWaterDemandM3: includeRainfall ? totalNetWaterDemandM3 : undefined,
        weeklyDetails: weeklyResults,
      };
    } catch (error) {
      logger.error('Failed to calculate seasonal water demand', error);
      throw error;
    }
  }

  /**
   * Get monthly ETo from database
   */
  private async getMonthlyETo(calendarWeek: number, year: number): Promise<number> {
    try {
      // Determine the month for this week
      const date = dayjs().year(year).week(calendarWeek);
      const month = date.month() + 1; // dayjs months are 0-indexed

      const query = `
        SELECT eto_value 
        FROM ros.eto_monthly 
        WHERE aos_station = 'นครราชสีมา' 
          AND province = 'นครราชสีมา'
          AND month = $1
      `;

      const result = await pool.query(query, [month]);
      
      if (result.rows.length === 0) {
        throw new Error(`No ETo data found for month ${month}`);
      }

      return result.rows[0].eto_value;
    } catch (error) {
      logger.error('Failed to get monthly ETo', error);
      throw error;
    }
  }

  /**
   * Calculate weekly ETo from monthly value
   */
  private calculateWeeklyETo(monthlyETo: number, calendarWeek: number, year: number): number {
    // Check if this week contains the first day of next month
    const weekStart = dayjs().year(year).week(calendarWeek).startOf('week');
    const weekEnd = dayjs().year(year).week(calendarWeek).endOf('week');
    
    if (weekStart.month() !== weekEnd.month()) {
      // Week spans two months, use next month's ETo
      // This is a simplified implementation - you may want to get the actual next month's ETo
      return monthlyETo / 4; // For now, just divide by 4
    }

    // Standard calculation: monthly ETo / 4
    return monthlyETo / 4;
  }

  /**
   * Get Kc value from database
   */
  private async getKcValue(cropType: CropType, cropWeek: number): Promise<number> {
    try {
      const query = `
        SELECT kc_value 
        FROM ros.kc_weekly 
        WHERE crop_type = $1 AND crop_week = $2
      `;

      const result = await pool.query(query, [cropType, cropWeek]);
      
      if (result.rows.length === 0) {
        throw new Error(`No Kc data found for ${cropType} week ${cropWeek}`);
      }

      return result.rows[0].kc_value;
    } catch (error) {
      logger.error('Failed to get Kc value', error);
      throw error;
    }
  }

  /**
   * Get total crop weeks for a crop type
   */
  private async getTotalCropWeeks(cropType: CropType): Promise<number> {
    try {
      const query = `
        SELECT MAX(crop_week) as max_week 
        FROM ros.kc_weekly 
        WHERE crop_type = $1
      `;

      const result = await pool.query(query, [cropType]);
      return result.rows[0]?.max_week || 16; // Default to 16 weeks
    } catch (error) {
      logger.error('Failed to get total crop weeks', error);
      throw error;
    }
  }

  /**
   * Save water demand calculation to database
   */
  private async saveWaterDemandCalculation(result: WaterDemandResult): Promise<void> {
    try {
      const query = `
        INSERT INTO ros.water_demand_calculations (
          area_id, area_type, area_rai, crop_type, crop_week,
          calendar_week, calendar_year, calculation_date,
          monthly_eto, weekly_eto, kc_value, percolation,
          crop_water_demand_mm, crop_water_demand_m3,
          effective_rainfall, water_level,
          net_water_demand_mm, net_water_demand_m3
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
          $11, $12, $13, $14, $15, $16, $17, $18
        )
      `;

      const values = [
        result.areaId,
        result.areaType,
        result.areaRai,
        result.cropType,
        result.cropWeek,
        result.calendarWeek,
        result.calendarYear,
        new Date(),
        result.monthlyETo,
        result.weeklyETo,
        result.kcValue,
        result.percolation,
        result.cropWaterDemandMm,
        result.cropWaterDemandM3,
        result.effectiveRainfall || null,
        result.waterLevel || null,
        result.netWaterDemandMm || null,
        result.netWaterDemandM3 || null,
      ];

      await pool.query(query, values);
    } catch (error) {
      logger.error('Failed to save water demand calculation', error);
      throw error;
    }
  }

  /**
   * Get historical water demand calculations
   */
  async getHistoricalWaterDemand(
    areaId: string,
    startDate: Date,
    endDate: Date
  ): Promise<WaterDemandResult[]> {
    try {
      const query = `
        SELECT * FROM ros.water_demand_calculations
        WHERE area_id = $1 
          AND calculation_date BETWEEN $2 AND $3
        ORDER BY calculation_date, crop_week
      `;

      const result = await pool.query(query, [areaId, startDate, endDate]);

      return result.rows.map(row => ({
        areaId: row.area_id,
        areaType: row.area_type,
        areaRai: parseFloat(row.area_rai),
        cropType: row.crop_type,
        cropWeek: row.crop_week,
        calendarWeek: row.calendar_week,
        calendarYear: row.calendar_year,
        monthlyETo: parseFloat(row.monthly_eto),
        weeklyETo: parseFloat(row.weekly_eto),
        kcValue: parseFloat(row.kc_value),
        percolation: parseFloat(row.percolation),
        cropWaterDemandMm: parseFloat(row.crop_water_demand_mm),
        cropWaterDemandM3: parseFloat(row.crop_water_demand_m3),
        effectiveRainfall: row.effective_rainfall ? parseFloat(row.effective_rainfall) : undefined,
        waterLevel: row.water_level ? parseFloat(row.water_level) : undefined,
        netWaterDemandMm: row.net_water_demand_mm ? parseFloat(row.net_water_demand_mm) : undefined,
        netWaterDemandM3: row.net_water_demand_m3 ? parseFloat(row.net_water_demand_m3) : undefined,
      }));
    } catch (error) {
      logger.error('Failed to get historical water demand', error);
      throw error;
    }
  }
}

export const waterDemandService = new WaterDemandService();