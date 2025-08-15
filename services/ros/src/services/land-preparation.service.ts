import { pool } from '@config/database';
import { CropType, WaterDemandResult } from '../types';
import { logger } from '@utils/logger';

export interface LandPreparationData {
  cropType: CropType;
  preparationWaterMm: number;
  preparationWeeks: number;
  description?: string;
}

export class LandPreparationService {
  private readonly RAI_TO_M3_FACTOR = 1.6;

  /**
   * Get land preparation water requirements for a crop type
   */
  async getLandPreparationRequirements(cropType: CropType): Promise<LandPreparationData> {
    try {
      const query = `
        SELECT 
          crop_type,
          preparation_water_mm,
          preparation_weeks,
          description
        FROM ros.land_preparation_water
        WHERE crop_type = $1
      `;

      const result = await pool.query(query, [cropType]);
      
      if (result.rows.length === 0) {
        // Default values if not in database
        const defaults: Record<CropType, LandPreparationData> = {
          rice: { cropType: 'rice', preparationWaterMm: 100, preparationWeeks: 1 },
          corn: { cropType: 'corn', preparationWaterMm: 50, preparationWeeks: 1 },
          sugarcane: { cropType: 'sugarcane', preparationWaterMm: 50, preparationWeeks: 1 },
        };
        
        logger.warn(`No land preparation data found for ${cropType}, using defaults`);
        return defaults[cropType];
      }

      return {
        cropType: result.rows[0].crop_type,
        preparationWaterMm: parseFloat(result.rows[0].preparation_water_mm),
        preparationWeeks: result.rows[0].preparation_weeks,
        description: result.rows[0].description,
      };
    } catch (error) {
      logger.error('Failed to get land preparation requirements', error);
      throw error;
    }
  }

  /**
   * Calculate land preparation water demand
   */
  async calculateLandPreparationDemand(
    cropType: CropType,
    areaRai: number,
    areaId: string,
    areaType: string,
    plantingDate: Date
  ): Promise<WaterDemandResult> {
    try {
      const landPrep = await this.getLandPreparationRequirements(cropType);
      
      // Calculate water volume
      const waterDemandM3 = landPrep.preparationWaterMm * areaRai * this.RAI_TO_M3_FACTOR;
      
      // Get calendar week for land preparation (week before planting)
      const prepDate = new Date(plantingDate);
      prepDate.setDate(prepDate.getDate() - 7); // 1 week before planting
      const calendarWeek = this.getWeekNumber(prepDate);
      const calendarYear = prepDate.getFullYear();

      const result: WaterDemandResult = {
        areaId,
        areaType: areaType as any,
        areaRai,
        cropType,
        cropWeek: 0, // Week 0 indicates land preparation
        calendarWeek,
        calendarYear,
        monthlyETo: 0, // Not applicable for land prep
        weeklyETo: 0,
        kcValue: 0,
        percolation: 0,
        cropWaterDemandMm: landPrep.preparationWaterMm,
        cropWaterDemandM3: waterDemandM3,
        // Land preparation typically doesn't account for rainfall
        effectiveRainfall: 0,
        netWaterDemandMm: landPrep.preparationWaterMm,
        netWaterDemandM3: waterDemandM3,
      };

      // Save to database
      await this.saveLandPreparationCalculation(result);

      return result;
    } catch (error) {
      logger.error('Failed to calculate land preparation demand', error);
      throw error;
    }
  }

  /**
   * Save land preparation calculation to database
   */
  private async saveLandPreparationCalculation(result: WaterDemandResult): Promise<void> {
    try {
      const query = `
        INSERT INTO ros.water_demand_calculations (
          area_id, area_type, area_rai, crop_type, crop_week,
          calendar_week, calendar_year, calculation_date,
          monthly_eto, weekly_eto, kc_value, percolation,
          crop_water_demand_mm, crop_water_demand_m3,
          effective_rainfall, net_water_demand_mm, net_water_demand_m3,
          is_land_preparation, land_preparation_mm, land_preparation_m3
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
          $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
        )
      `;

      const values = [
        result.areaId,
        result.areaType,
        result.areaRai,
        result.cropType,
        0, // crop_week = 0 for land preparation
        result.calendarWeek,
        result.calendarYear,
        new Date(),
        0, // monthly_eto
        0, // weekly_eto
        0, // kc_value
        0, // percolation
        result.cropWaterDemandMm,
        result.cropWaterDemandM3,
        0, // effective_rainfall
        result.netWaterDemandMm,
        result.netWaterDemandM3,
        true, // is_land_preparation
        result.cropWaterDemandMm, // land_preparation_mm
        result.cropWaterDemandM3, // land_preparation_m3
      ];

      await pool.query(query, values);
    } catch (error) {
      logger.error('Failed to save land preparation calculation', error);
      throw error;
    }
  }

  /**
   * Get week number from date
   */
  private getWeekNumber(date: Date): number {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  }
}

export const landPreparationService = new LandPreparationService();