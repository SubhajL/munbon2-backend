import { pool } from '@config/database';
import { logger } from '@utils/logger';
import axios from 'axios';
import { config } from '@config/index';

export interface RainfallData {
  date: Date;
  areaId: string;
  rainfallMm: number;
  effectiveRainfallMm: number;
  source: 'manual' | 'weather_api' | 'sensor';
}

export class RainfallService {
  /**
   * Get effective rainfall for a specific area and date
   * Effective rainfall = Total rainfall * efficiency factor
   */
  async getEffectiveRainfall(
    areaId: string,
    date: Date,
    efficiencyFactor: number = 0.8
  ): Promise<number> {
    try {
      // First, check if we have manual rainfall data
      const manualRainfall = await this.getManualRainfall(areaId, date);
      if (manualRainfall !== null) {
        return manualRainfall * efficiencyFactor;
      }

      // If no manual data, try to get from weather service
      const weatherRainfall = await this.getWeatherServiceRainfall(areaId, date);
      if (weatherRainfall !== null) {
        return weatherRainfall * efficiencyFactor;
      }

      // No rainfall data available
      return 0;
    } catch (error) {
      logger.error('Failed to get effective rainfall', error);
      return 0; // Default to 0 if error
    }
  }

  /**
   * Get weekly effective rainfall
   */
  async getWeeklyEffectiveRainfall(
    areaId: string,
    weekStartDate: Date,
    efficiencyFactor: number = 0.8
  ): Promise<number> {
    try {
      let totalRainfall = 0;

      // Get rainfall for each day of the week
      for (let i = 0; i < 7; i++) {
        const date = new Date(weekStartDate);
        date.setDate(date.getDate() + i);
        
        const dailyRainfall = await this.getEffectiveRainfall(areaId, date, 1.0); // Get raw rainfall
        totalRainfall += dailyRainfall;
      }

      // Apply efficiency factor to weekly total
      return totalRainfall * efficiencyFactor;
    } catch (error) {
      logger.error('Failed to get weekly effective rainfall', error);
      return 0;
    }
  }

  /**
   * Save rainfall data manually
   */
  async saveRainfallData(data: RainfallData): Promise<void> {
    try {
      const query = `
        INSERT INTO ros.rainfall_data (
          area_id, date, rainfall_mm, effective_rainfall_mm, source
        ) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (area_id, date) 
        DO UPDATE SET 
          rainfall_mm = EXCLUDED.rainfall_mm,
          effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
          source = EXCLUDED.source,
          updated_at = NOW()
      `;

      await pool.query(query, [
        data.areaId,
        data.date,
        data.rainfallMm,
        data.effectiveRainfallMm,
        data.source,
      ]);

      logger.info('Rainfall data saved', { areaId: data.areaId, date: data.date });
    } catch (error) {
      logger.error('Failed to save rainfall data', error);
      throw error;
    }
  }

  /**
   * Get manual rainfall data from database
   */
  private async getManualRainfall(areaId: string, date: Date): Promise<number | null> {
    try {
      const query = `
        SELECT rainfall_mm 
        FROM ros.rainfall_data 
        WHERE area_id = $1 AND date = $2
      `;

      const result = await pool.query(query, [areaId, date]);
      
      if (result.rows.length > 0) {
        return result.rows[0].rainfall_mm;
      }

      return null;
    } catch (error) {
      logger.error('Failed to get manual rainfall', error);
      return null;
    }
  }

  /**
   * Get rainfall from weather service
   */
  private async getWeatherServiceRainfall(areaId: string, date: Date): Promise<number | null> {
    try {
      // Get area location
      const areaQuery = `
        SELECT aos_station, province 
        FROM area_info 
        WHERE area_id = $1
      `;
      const areaResult = await pool.query(areaQuery, [areaId]);
      
      if (areaResult.rows.length === 0) {
        return null;
      }

      // Call weather service (this would be a real API call)
      // For now, return null as placeholder
      // In production, this would call the weather service API
      
      return null;
    } catch (error) {
      logger.error('Failed to get weather service rainfall', error);
      return null;
    }
  }

  /**
   * Import historical rainfall data
   */
  async importHistoricalRainfall(
    data: Array<{
      areaId: string;
      date: Date;
      rainfallMm: number;
    }>,
    efficiencyFactor: number = 0.8
  ): Promise<void> {
    try {
      for (const record of data) {
        await this.saveRainfallData({
          date: record.date,
          areaId: record.areaId,
          rainfallMm: record.rainfallMm,
          effectiveRainfallMm: record.rainfallMm * efficiencyFactor,
          source: 'manual',
        });
      }

      logger.info(`Imported ${data.length} rainfall records`);
    } catch (error) {
      logger.error('Failed to import historical rainfall', error);
      throw error;
    }
  }

  /**
   * Get rainfall statistics for an area
   */
  async getRainfallStatistics(
    areaId: string,
    startDate: Date,
    endDate: Date
  ): Promise<{
    totalRainfall: number;
    averageDailyRainfall: number;
    rainyDays: number;
    maxDailyRainfall: number;
  }> {
    try {
      const query = `
        SELECT 
          SUM(rainfall_mm) as total_rainfall,
          AVG(rainfall_mm) as avg_rainfall,
          COUNT(CASE WHEN rainfall_mm > 0 THEN 1 END) as rainy_days,
          MAX(rainfall_mm) as max_rainfall
        FROM ros.rainfall_data
        WHERE area_id = $1 
          AND date BETWEEN $2 AND $3
      `;

      const result = await pool.query(query, [areaId, startDate, endDate]);
      const row = result.rows[0];

      return {
        totalRainfall: parseFloat(row.total_rainfall) || 0,
        averageDailyRainfall: parseFloat(row.avg_rainfall) || 0,
        rainyDays: parseInt(row.rainy_days) || 0,
        maxDailyRainfall: parseFloat(row.max_rainfall) || 0,
      };
    } catch (error) {
      logger.error('Failed to get rainfall statistics', error);
      throw error;
    }
  }
}

export const rainfallService = new RainfallService();