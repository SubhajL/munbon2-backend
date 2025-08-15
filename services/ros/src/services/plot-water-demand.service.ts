import { pool } from '@config/database';
import { logger } from '@utils/logger';
import { waterDemandService } from './water-demand.service';
import { WaterDemandInput, WaterDemandResult, SeasonalWaterDemandResult, CropType } from '../types';

export interface PlotInfo {
  plotId: string;
  plotCode?: string;
  areaRai: number;
  parentSectionId?: string;
  parentZoneId?: string;
  aosStation: string;
  province: string;
}

export interface PlotCropSchedule {
  plotId: string;
  cropType: CropType;
  plantingDate: Date;
  expectedHarvestDate?: Date;
  season: 'wet' | 'dry';
  year: number;
  status: 'planned' | 'active' | 'harvested';
}

export interface PlotWaterDemandInput {
  plotId: string;
  cropType: CropType;
  plantingDate: Date;
  includeRainfall?: boolean;
  includeLandPreparation?: boolean;
}

export interface BatchPlotWaterDemandInput {
  plotIds: string[];
  cropType: CropType;
  plantingDate: Date;
  includeRainfall?: boolean;
  includeLandPreparation?: boolean;
}

export class PlotWaterDemandService {
  /**
   * Get plot information
   */
  async getPlotInfo(plotId: string): Promise<PlotInfo | null> {
    try {
      const query = `
        SELECT 
          plot_id,
          plot_code,
          area_rai,
          parent_section_id,
          parent_zone_id,
          aos_station,
          province
        FROM ros.plots
        WHERE plot_id = $1
      `;

      const result = await pool.query(query, [plotId]);
      
      if (result.rows.length === 0) {
        return null;
      }

      const row = result.rows[0];
      return {
        plotId: row.plot_id,
        plotCode: row.plot_code,
        areaRai: parseFloat(row.area_rai),
        parentSectionId: row.parent_section_id,
        parentZoneId: row.parent_zone_id,
        aosStation: row.aos_station,
        province: row.province,
      };
    } catch (error) {
      logger.error('Failed to get plot info', error);
      throw error;
    }
  }

  /**
   * Calculate water demand for a single plot
   */
  async calculatePlotWaterDemand(input: PlotWaterDemandInput): Promise<SeasonalWaterDemandResult> {
    try {
      // Get plot information
      const plotInfo = await this.getPlotInfo(input.plotId);
      if (!plotInfo) {
        throw new Error(`Plot ${input.plotId} not found`);
      }

      // Calculate seasonal water demand using existing service
      const result = await waterDemandService.calculateSeasonalWaterDemand(
        input.plotId,
        'plot', // area type
        plotInfo.areaRai,
        input.cropType,
        input.plantingDate,
        input.includeRainfall ?? true,
        input.includeLandPreparation ?? true
      );

      // Save to plot-specific tables
      await this.savePlotSeasonalDemand(plotInfo, input, result);
      await this.savePlotWeeklyDemands(plotInfo, input, result);

      return result;
    } catch (error) {
      logger.error('Failed to calculate plot water demand', error);
      throw error;
    }
  }

  /**
   * Calculate water demand for multiple plots (batch)
   */
  async calculateBatchPlotWaterDemand(input: BatchPlotWaterDemandInput): Promise<Map<string, SeasonalWaterDemandResult>> {
    try {
      const results = new Map<string, SeasonalWaterDemandResult>();
      
      // Process plots in parallel batches
      const batchSize = 10;
      for (let i = 0; i < input.plotIds.length; i += batchSize) {
        const batch = input.plotIds.slice(i, i + batchSize);
        
        const batchPromises = batch.map(plotId => 
          this.calculatePlotWaterDemand({
            plotId,
            cropType: input.cropType,
            plantingDate: input.plantingDate,
            includeRainfall: input.includeRainfall,
            includeLandPreparation: input.includeLandPreparation,
          }).then(result => ({ plotId, result }))
          .catch(error => {
            logger.error(`Failed to calculate for plot ${plotId}`, error);
            return null;
          })
        );

        const batchResults = await Promise.all(batchPromises);
        
        for (const item of batchResults) {
          if (item) {
            results.set(item.plotId, item.result);
          }
        }
      }

      return results;
    } catch (error) {
      logger.error('Failed to calculate batch plot water demand', error);
      throw error;
    }
  }

  /**
   * Get water demand for plots by zone or section
   */
  async getPlotsByArea(areaType: 'zone' | 'section', areaId: string): Promise<PlotInfo[]> {
    try {
      const column = areaType === 'zone' ? 'parent_zone_id' : 'parent_section_id';
      
      const query = `
        SELECT 
          plot_id,
          plot_code,
          area_rai,
          parent_section_id,
          parent_zone_id,
          aos_station,
          province
        FROM ros.plots
        WHERE ${column} = $1
        ORDER BY plot_id
      `;

      const result = await pool.query(query, [areaId]);
      
      return result.rows.map(row => ({
        plotId: row.plot_id,
        plotCode: row.plot_code,
        areaRai: parseFloat(row.area_rai),
        parentSectionId: row.parent_section_id,
        parentZoneId: row.parent_zone_id,
        aosStation: row.aos_station,
        province: row.province,
      }));
    } catch (error) {
      logger.error('Failed to get plots by area', error);
      throw error;
    }
  }

  /**
   * Save plot seasonal demand to database
   */
  private async savePlotSeasonalDemand(
    plotInfo: PlotInfo, 
    input: PlotWaterDemandInput,
    result: SeasonalWaterDemandResult
  ): Promise<void> {
    try {
      const query = `
        INSERT INTO ros.plot_water_demand_seasonal (
          plot_id, crop_type, planting_date, harvest_date,
          season, year, area_rai, total_crop_weeks,
          total_water_demand_mm, total_water_demand_m3,
          land_preparation_mm, land_preparation_m3,
          total_effective_rainfall_mm, total_net_water_demand_mm,
          total_net_water_demand_m3, includes_land_preparation,
          includes_rainfall
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
          $11, $12, $13, $14, $15, $16, $17
        )
        ON CONFLICT (plot_id, crop_type, planting_date)
        DO UPDATE SET
          harvest_date = EXCLUDED.harvest_date,
          total_water_demand_mm = EXCLUDED.total_water_demand_mm,
          total_water_demand_m3 = EXCLUDED.total_water_demand_m3,
          land_preparation_mm = EXCLUDED.land_preparation_mm,
          land_preparation_m3 = EXCLUDED.land_preparation_m3,
          total_effective_rainfall_mm = EXCLUDED.total_effective_rainfall_mm,
          total_net_water_demand_mm = EXCLUDED.total_net_water_demand_mm,
          total_net_water_demand_m3 = EXCLUDED.total_net_water_demand_m3,
          updated_at = NOW()
      `;

      const season = this.determineSeason(input.plantingDate);
      const year = input.plantingDate.getFullYear();

      const values = [
        input.plotId,
        input.cropType,
        input.plantingDate,
        result.harvestDate,
        season,
        year,
        plotInfo.areaRai,
        result.totalCropWeeks,
        result.totalWaterDemandMm,
        result.totalWaterDemandM3,
        result.landPreparationMm || null,
        result.landPreparationM3 || null,
        result.totalEffectiveRainfall || null,
        result.totalNetWaterDemandMm || null,
        result.totalNetWaterDemandM3 || null,
        input.includeLandPreparation ?? true,
        input.includeRainfall ?? true,
      ];

      await pool.query(query, values);
    } catch (error) {
      logger.error('Failed to save plot seasonal demand', error);
      throw error;
    }
  }

  /**
   * Save plot weekly demands to database
   */
  private async savePlotWeeklyDemands(
    plotInfo: PlotInfo,
    input: PlotWaterDemandInput,
    result: SeasonalWaterDemandResult
  ): Promise<void> {
    try {
      if (!result.weeklyDetails) return;

      for (const weekData of result.weeklyDetails) {
        const query = `
          INSERT INTO ros.plot_water_demand_weekly (
            plot_id, crop_type, crop_week, calendar_week,
            calendar_year, calculation_date, area_rai,
            monthly_eto, weekly_eto, kc_value, percolation,
            crop_water_demand_mm, crop_water_demand_m3,
            effective_rainfall_mm, net_water_demand_mm,
            net_water_demand_m3, is_land_preparation
          ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17
          )
          ON CONFLICT (plot_id, crop_type, crop_week, calendar_year, calendar_week)
          DO UPDATE SET
            crop_water_demand_mm = EXCLUDED.crop_water_demand_mm,
            crop_water_demand_m3 = EXCLUDED.crop_water_demand_m3,
            effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
            net_water_demand_mm = EXCLUDED.net_water_demand_mm,
            net_water_demand_m3 = EXCLUDED.net_water_demand_m3
        `;

        const values = [
          input.plotId,
          input.cropType,
          weekData.cropWeek,
          weekData.calendarWeek,
          weekData.calendarYear,
          new Date(),
          plotInfo.areaRai,
          weekData.monthlyETo,
          weekData.weeklyETo,
          weekData.kcValue,
          weekData.percolation,
          weekData.cropWaterDemandMm,
          weekData.cropWaterDemandM3,
          weekData.effectiveRainfall || null,
          weekData.netWaterDemandMm || null,
          weekData.netWaterDemandM3 || null,
          weekData.cropWeek === 0, // is_land_preparation
        ];

        await pool.query(query, values);
      }
    } catch (error) {
      logger.error('Failed to save plot weekly demands', error);
      throw error;
    }
  }

  /**
   * Determine season based on planting date
   */
  private determineSeason(date: Date): 'wet' | 'dry' {
    const month = date.getMonth() + 1; // 0-indexed
    // Wet season: May-October (months 5-10)
    // Dry season: November-April (months 11-12, 1-4)
    return (month >= 5 && month <= 10) ? 'wet' : 'dry';
  }

  /**
   * Get historical water demand for a plot
   */
  async getPlotHistoricalDemand(
    plotId: string,
    startYear?: number,
    endYear?: number
  ): Promise<any[]> {
    try {
      let query = `
        SELECT * FROM ros.plot_water_demand_seasonal
        WHERE plot_id = $1
      `;
      
      const params: any[] = [plotId];
      
      if (startYear) {
        query += ` AND year >= $${params.length + 1}`;
        params.push(startYear);
      }
      
      if (endYear) {
        query += ` AND year <= $${params.length + 1}`;
        params.push(endYear);
      }
      
      query += ` ORDER BY year, season`;

      const result = await pool.query(query, params);
      return result.rows;
    } catch (error) {
      logger.error('Failed to get plot historical demand', error);
      throw error;
    }
  }

  /**
   * Get current week water demand for active plots
   */
  async getCurrentWeekDemandForActivePlots(currentWeek: number, currentYear: number): Promise<any[]> {
    try {
      const query = `
        SELECT 
          pwd.*,
          p.plot_code,
          p.parent_section_id,
          p.parent_zone_id
        FROM ros.plot_water_demand_weekly pwd
        JOIN ros.plots p ON p.plot_id = pwd.plot_id
        WHERE pwd.calendar_week = $1
          AND pwd.calendar_year = $2
          AND pwd.is_land_preparation = FALSE
        ORDER BY p.parent_zone_id, p.parent_section_id, p.plot_id
      `;

      const result = await pool.query(query, [currentWeek, currentYear]);
      return result.rows;
    } catch (error) {
      logger.error('Failed to get current week demand', error);
      throw error;
    }
  }
}

export const plotWaterDemandService = new PlotWaterDemandService();