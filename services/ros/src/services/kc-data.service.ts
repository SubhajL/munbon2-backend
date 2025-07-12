import { pool } from '@config/database';
import { CropType } from '@types/index';
import { logger } from '@utils/logger';

export class KcDataService {
  /**
   * Get Kc value for specific crop and week
   */
  async getKcValue(cropType: CropType, cropWeek: number): Promise<number> {
    try {
      const query = `
        SELECT kc_value 
        FROM kc_weekly 
        WHERE crop_type = $1 AND crop_week = $2
      `;

      const result = await pool.query(query, [cropType, cropWeek]);
      
      if (result.rows.length === 0) {
        throw new Error(`No Kc data found for ${cropType} week ${cropWeek}`);
      }

      return parseFloat(result.rows[0].kc_value);
    } catch (error) {
      logger.error('Failed to get Kc value', error);
      throw error;
    }
  }

  /**
   * Get all Kc values for a crop type
   */
  async getAllKcValues(cropType: CropType): Promise<Array<{ cropWeek: number; kcValue: number }>> {
    try {
      const query = `
        SELECT crop_week, kc_value 
        FROM kc_weekly 
        WHERE crop_type = $1
        ORDER BY crop_week
      `;

      const result = await pool.query(query, [cropType]);
      
      return result.rows.map(row => ({
        cropWeek: row.crop_week,
        kcValue: parseFloat(row.kc_value),
      }));
    } catch (error) {
      logger.error('Failed to get all Kc values', error);
      throw error;
    }
  }

  /**
   * Get total crop weeks for a crop type
   */
  async getTotalCropWeeks(cropType: CropType): Promise<number> {
    try {
      const query = `
        SELECT MAX(crop_week) as max_week 
        FROM kc_weekly 
        WHERE crop_type = $1
      `;

      const result = await pool.query(query, [cropType]);
      
      if (result.rows.length === 0 || !result.rows[0].max_week) {
        // Default crop weeks
        const defaults: Record<CropType, number> = {
          rice: 16,
          corn: 16,
          sugarcane: 52,
        };
        return defaults[cropType];
      }

      return result.rows[0].max_week;
    } catch (error) {
      logger.error('Failed to get total crop weeks', error);
      throw error;
    }
  }

  /**
   * Upload Kc data from Excel (to be implemented)
   */
  async uploadKcData(data: Array<{
    cropType: CropType;
    cropWeek: number;
    kcValue: number;
  }>): Promise<void> {
    try {
      const query = `
        INSERT INTO kc_weekly (crop_type, crop_week, kc_value)
        VALUES ($1, $2, $3)
        ON CONFLICT (crop_type, crop_week)
        DO UPDATE SET 
          kc_value = EXCLUDED.kc_value,
          updated_at = NOW()
      `;

      for (const row of data) {
        await pool.query(query, [
          row.cropType,
          row.cropWeek,
          row.kcValue,
        ]);
      }

      logger.info(`Uploaded ${data.length} Kc records`);
    } catch (error) {
      logger.error('Failed to upload Kc data', error);
      throw error;
    }
  }

  /**
   * Get crop information summary
   */
  async getCropSummary(): Promise<Array<{
    cropType: CropType;
    totalWeeks: number;
    kcRange: { min: number; max: number };
  }>> {
    try {
      const query = `
        SELECT 
          crop_type,
          COUNT(*) as total_weeks,
          MIN(kc_value) as min_kc,
          MAX(kc_value) as max_kc
        FROM kc_weekly
        GROUP BY crop_type
        ORDER BY crop_type
      `;

      const result = await pool.query(query);
      
      return result.rows.map(row => ({
        cropType: row.crop_type,
        totalWeeks: parseInt(row.total_weeks),
        kcRange: {
          min: parseFloat(row.min_kc),
          max: parseFloat(row.max_kc),
        },
      }));
    } catch (error) {
      logger.error('Failed to get crop summary', error);
      throw error;
    }
  }
}

export const kcDataService = new KcDataService();